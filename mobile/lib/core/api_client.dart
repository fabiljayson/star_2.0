import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Parsed error envelope from STAR's standard error body:
/// {"error": {"code": "...", "message": "...", "details": {...}}}.
class ApiException implements Exception {
  ApiException(this.status, {this.code, this.message, this.details});
  final int status;
  final String? code;
  final String? message;
  final Map<String, dynamic>? details;

  String get friendlyMessage => message ?? 'Request failed (HTTP $status).';

  @override
  String toString() => 'ApiException($status, $code, $message)';
}

/// Token plumbing the client needs from its session owner.
abstract class ApiTokenSource {
  String? accessToken();
  String? refreshToken();

  /// Persist the rotated pair delivered by `auth/token/refresh/`.
  Future<void> tokensRefreshed(Map<String, dynamic> tokens);

  /// All outstanding tokens are dead (revoked / rejected by the server).
  void sessionExpired();
}

/// HTTP client for the STAR API.
///
/// - Every request carries `Authorization: Bearer <accessToken>` (if known).
/// - On a JSON request answered 401, the client refreshes the token pair once
///   and replays the original request. Parallel 401s share a single refresh.
/// - Auth endpoints (login / refresh) are never retried.
/// - Multipart uploads are not retried; the caller owns the file stream.
class ApiClient {
  ApiClient({
    required this.baseUrl,
    required this.tokens,
    http.Client? httpClient,
  }) : _http = httpClient ?? http.Client();

  static const _authPrefixes = [
    'auth/login/',
    'auth/token/refresh/',
    'auth/mfa/verify/',
    'auth/register/',
  ];

  String baseUrl;
  final ApiTokenSource tokens;
  final http.Client _http;

  Future<bool>? _refreshInFlight;

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = Uri.parse(baseUrl);
    final normalized = base.path.endsWith('/')
        ? base.path.substring(0, base.path.length - 1)
        : base.path;
    return base.replace(
      path: '$normalized${path.startsWith('/') ? path : '/$path'}',
      queryParameters: query == null || query.isEmpty ? null : query,
    );
  }

  Future<Map<String, String>> _headers({bool json = true}) => Future.value({
        'Accept': 'application/json',
        if (json) 'Content-Type': 'application/json',
        if (tokens.accessToken() != null)
          'Authorization': 'Bearer ${tokens.accessToken()}',
      });

  // ── JSON helpers ───────────────────────────────────────────────────────
  Future<dynamic> getJson(String path, {Map<String, String>? query}) =>
      _send('GET', path, null, query: query);

  Future<dynamic> postJson(String path, {Object? body}) =>
      _send('POST', path, body);

  Future<dynamic> patchJson(String path, Object body) => _send('PATCH', path, body);

  Future<dynamic> putJson(String path, Object body) => _send('PUT', path, body);

  Future<dynamic> deleteJson(String path) => _send('DELETE', path, null);

  Future<dynamic> _send(
    String method,
    String path,
    Object? body, {
    Map<String, String>? query,
    bool forAuthRoute = false,
  }) async {
    final isAuthRoute = forAuthRoute ||
        _authPrefixes.any((prefix) => path.startsWith(prefix));

    Future<http.Response> perform() => () async {
          final request = http.Request(method, _uri(path, query))
            ..headers.addAll(await _headers())
            ..body = body == null ? '' : jsonEncode(body);
          return _http.send(request).then(http.Response.fromStream);
        }();

    var response = await perform();
    var decoded = _decode(response);
    if (response.statusCode == 401 && !isAuthRoute) {
      final refreshed = await refreshOnce();
      if (refreshed) {
        response = await perform();
        decoded = _decode(response);
        // Final answer for this request: the replay is never refreshed
        // again, so a server stuck on 401 cannot loop us forever.
        _throwIfError(response, decoded);
        return decoded;
      }
    }
    _throwIfError(response, decoded);
    return decoded;
  }

  void _throwIfError(http.Response response, dynamic decoded) {
    if (response.statusCode >= 400) {
      throw _exceptionFrom(response, decoded);
    }
  }

  /// Multipart upload. Returned decoded JSON (or null on 204).
  /// A 401 here triggers refresh but never a retry (the file stream is gone).
  Future<dynamic> upload(
    String path, {
    required String fileField,
    required List<int> bytes,
    required String fileName,
    String contentType = 'application/octet-stream',
    Map<String, String> fields = const {},
  }) async {
    final request = http.MultipartRequest('POST', _uri(path))
      ..files.add(http.MultipartFile.fromBytes(fileField, bytes,
          filename: fileName))
      ..fields.addAll(fields);
    request.headers['Authorization'] = 'Bearer ${tokens.accessToken() ?? ''}';

    final response = await http.Response.fromStream(await _http.send(request));
    final decoded = _decode(response);
    if (response.statusCode == 401) {
      final refreshed = await refreshOnce();
      if (refreshed) {
        throw ApiException(response.statusCode, code: 'retried_upload');
      }
    }
    if (response.statusCode >= 400) {
      throw _exceptionFrom(response, decoded);
    }
    return decoded;
  }

  /// Single-flight refresh: concurrent callers await the same attempt.
  /// Returns true when a fresh access token is now usable.
  Future<bool> refreshOnce() {
    final existing = _refreshInFlight;
    if (existing != null) return existing;
    final attempt = _doRefresh();
    _refreshInFlight = attempt;
    return attempt.whenComplete(() => _refreshInFlight = null);
  }

  Future<bool> _doRefresh() async {
    final refresh = tokens.refreshToken();
    if (refresh == null || refresh.isEmpty) {
      tokens.sessionExpired();
      return false;
    }
    final http.Response response;
    try {
      response = await _http.post(
        _uri('auth/token/refresh/'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh': refresh}),
      );
    } catch (_) {
      tokens.sessionExpired();
      return false;
    }
    if (response.statusCode != 200) {
      tokens.sessionExpired();
      return false;
    }
    final data = _decode(response);
    if (data case {'access': String()}) {
      await tokens.tokensRefreshed(data as Map<String, dynamic>);
      return true;
    }
    tokens.sessionExpired();
    return false;
  }

  // ── Parsing ────────────────────────────────────────────────────────────
  dynamic _decode(http.Response response) => response.body.isEmpty
      ? null
      : jsonDecode(utf8.decode(response.bodyBytes, allowMalformed: true));

  ApiException _exceptionFrom(http.Response response, dynamic decoded) {
    if (decoded is Map<String, dynamic> && decoded['error'] is Map) {
      final envelope = decoded['error'] as Map<String, dynamic>;
      return ApiException(
        response.statusCode,
        code: envelope['code'] as String?,
        message: envelope['message'] as String?,
        details: envelope['details'] is Map<String, dynamic>
            ? envelope['details'] as Map<String, dynamic>
            : null,
      );
    }
    if (decoded is Map<String, dynamic>) {
      return ApiException(
        response.statusCode,
        message: (decoded['detail'] ??
                decoded['message'] ??
                'Unexpected error from the API.')
            .toString(),
      );
    }
    return ApiException(response.statusCode);
  }
}
