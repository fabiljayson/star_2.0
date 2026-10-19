import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'session_store.dart';

enum AuthPhase { restoring, signedOut, requiresMfa, signedIn }

class StarUser {
  StarUser({
    required this.id,
    required this.email,
    required this.fullName,
    required this.isVerified,
    required this.isPlatformAdmin,
    required this.roles,
  });

  final String id;
  final String email;
  final String fullName;
  final bool isVerified;
  final bool isPlatformAdmin;
  final List<Map<String, dynamic>> roles;

  List<String> get roleNames =>
      roles.map((role) => '${role['role']}').toList();

  factory StarUser.fromJson(Map<String, dynamic> json) => StarUser(
        id: '${json['id']}',
        email: json['email'] as String,
        fullName: (json['full_name'] ?? '').toString(),
        isVerified: json['is_verified'] == true,
        isPlatformAdmin: json['is_platform_admin'] == true,
        roles: (json['roles'] as List<dynamic>? ?? [])
            .cast<Map<String, dynamic>>(),
      );
}

/// Session owner: persistence, login/MFA flow, token refresh and logout.
///
/// Listens (`sessionStream`) for hard session loss (revoked refresh token,
/// password change, logout-everywhere) to push the app back to sign-in.
class AppSession extends ChangeNotifier implements ApiTokenSource {
  AppSession({
    required this.store,
    this.clientFactory,
  }) {
    _client = clientFactory?.call(this) ??
        ApiClient(baseUrl: _apiBaseFallback, tokens: this);
  }

  static const _apiBaseFallback = 'http://10.0.2.2:8002/api/v1';

  final SessionStore store;
  final ApiClient Function(AppSession session)? clientFactory;

  late final ApiClient _client;
  ApiClient get api => _client;

  AuthPhase phase = AuthPhase.restoring;
  StarUser? user;
  bool onboardingDone = true;

  String? _accessToken;
  String? _refreshToken;
  String? _mfaToken;
  String serverUrl = _apiBaseFallback;

  final StreamController<AuthPhase> _phaseStream =
      StreamController<AuthPhase>.broadcast();

  Stream<AuthPhase> get phaseStream => _phaseStream.stream;

  /// Bootstrap: restore persisted session (verifying it still works),
  /// otherwise fall back to signed-out.
  Future<void> restore() async {
    serverUrl = await store.loadServerUrl() ?? _apiBaseFallback;
    _client.baseUrl = serverUrl;
    onboardingDone = await store.isOnboardingDone();
    final stored = await store.load();
    if (stored == null) {
      _setPhase(AuthPhase.signedOut);
      return;
    }
    _accessToken = stored.accessToken;
    _refreshToken = stored.refreshToken;
    user = StarUser.fromJson(stored.user);
    try {
      final me = await _client.getJson('users/me/');
      user = StarUser.fromJson(_asMap(me));
      _setPhase(AuthPhase.signedIn);
    } on ApiException catch (error) {
      if (error.status == 401) {
        // refreshOnce was driven by the client; if it could not restore us
        // the shared token source has already signalled expiration.
        return;
      }
      // Network/server trouble: keep the stored session but surface it.
      _setPhase(AuthPhase.signedOut);
    } catch (_) {
      _setPhase(AuthPhase.signedOut);
    }
  }

  /// Step 1 — email + password. May complete the login or require MFA.
  Future<void> login(String email, String password) async {
    final data = _asMap(
      await _client.postJson(
        'auth/login/',
        body: {'email': email, 'password': password},
      ),
    );
    if (data['mfa_required'] == true) {
      _mfaToken = data['mfa_token'] as String;
      _setPhase(AuthPhase.requiresMfa);
      return;
    }
    await _applyTokens(data);
  }

  /// Step 2 — TOTP code for users with MFA enabled.
  Future<void> verifyMfa(String code) async {
    if (_mfaToken == null) {
      throw StateError('No MFA challenge in progress.');
    }
    final data = _asMap(
      await _client.postJson('auth/mfa/verify/', body: {
        'mfa_token': _mfaToken,
        'code': code.trim(),
      }),
    );
    _mfaToken = null;
    await _applyTokens(data);
  }

  /// Leave the MFA challenge back to the sign-in form.
  void cancelMfa() {
    _mfaToken = null;
    _setPhase(AuthPhase.signedOut);
  }

  /// Mark the first-launch tour as seen (persists across restarts).
  Future<void> completeOnboarding() async {
    onboardingDone = true;
    await store.markOnboardingDone();
    notifyListeners();
  }

  Future<void> _applyTokens(Map<String, dynamic> data) async {
    final access = data['access'] as String?;
    final refresh = data['refresh'] as String?;
    final userJson = data['user'];
    if (access == null || refresh == null || userJson is! Map<String, dynamic>) {
      throw ApiException(
        422,
        code: 'malformed_login_response',
        message: 'The server answer was missing token or user data.',
      );
    }
    _accessToken = access;
    _refreshToken = refresh;
    user = StarUser.fromJson(userJson);
    await store.save(StoredSession(
      accessToken: access,
      refreshToken: refresh,
      user: userJson,
    ));
    _setPhase(AuthPhase.signedIn);
  }

  Future<void> updateServerUrl(String? url) async {
    final normalized = (url == null || url.trim().isEmpty)
        ? _apiBaseFallback
        : url.trim().replaceFirst(RegExp(r'/*$'), '');
    serverUrl = normalized;
    _client.baseUrl = normalized;
    await store.saveServerUrl(normalized);
    // A different server invalidates the cached session.
    if (phase == AuthPhase.signedIn || phase == AuthPhase.requiresMfa) {
      await _discardLocally();
      _setPhase(AuthPhase.signedOut);
    }
    notifyListeners();
  }

  Future<void> logout() async {
    try {
      await _client.postJson('auth/logout/', body: {});
    } catch (_) {
      // Network or 4xx: sign out locally regardless (session wins).
    } finally {
      await _discardLocally();
      _setPhase(AuthPhase.signedOut);
    }
  }

  Future<void> _discardLocally() async {
    _accessToken = null;
    _refreshToken = null;
    _mfaToken = null;
    user = null;
    await store.clear();
  }

  void _setPhase(AuthPhase value) {
    phase = value;
    if (!_phaseStream.isClosed) _phaseStream.add(value);
    notifyListeners();
  }

  // ── ApiTokenSource ─────────────────────────────────────────────────────
  @override
  String? accessToken() => _accessToken;

  @override
  String? refreshToken() => _refreshToken;

  @override
  Future<void> tokensRefreshed(Map<String, dynamic> tokens) async {
    final access = tokens['access'] as String?;
    final refresh = tokens['refresh'] as String?;
    if (access == null || refresh == null) return;
    _accessToken = access;
    _refreshToken = refresh;
    final stored = await store.load();
    if (stored != null) {
      await store.save(StoredSession(
        accessToken: access,
        refreshToken: refresh,
        user: stored.user,
      ));
    }
    notifyListeners();
  }

  @override
  void sessionExpired() {
    Future.microtask(() async {
      await _discardLocally();
      _mfaToken = null;
      user = null;
      _setPhase(AuthPhase.signedOut);
    });
  }

  static Map<String, dynamic> _asMap(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    return (value as Map).cast<String, dynamic>();
  }
}
