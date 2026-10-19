import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:star_mobile/core/api_client.dart';

class FakeTokens implements ApiTokenSource {
  FakeTokens({this.access, this.refresh});
  String? access;
  String? refresh;
  int expiredCallbacks = 0;
  int refreshApplied = 0;

  @override
  String? accessToken() => access;

  @override
  String? refreshToken() => refresh;

  @override
  Future<void> tokensRefreshed(Map<String, dynamic> tokens) async {
    refreshApplied += 1;
    access = tokens['access'] as String?;
    refresh = tokens['refresh'] as String?;
  }

  @override
  void sessionExpired() => expiredCallbacks += 1;
}

ApiClient _client(http.Client httpClient, FakeTokens tokens) =>
    ApiClient(baseUrl: 'http://test.local/api/v1', tokens: tokens, httpClient: httpClient);

void main() {
  group('ApiClient JSON requests', () {
    test('sends Bearer token when available', () async {
      final tokens = FakeTokens(access: 'abc', refresh: 'r1');
      String? seenAuth;
      final client = _client(
        MockClient((request) async {
          seenAuth = request.headers['Authorization'];
          return http.Response(jsonEncode({'ok': true}), 200);
        }),
        tokens,
      );
      final data = await client.getJson('procedures/');
      expect(seenAuth, 'Bearer abc');
      expect(data, {'ok': true});
    });

    test('refreshes once and replays the request after a 401', () async {
      final tokens = FakeTokens(access: 'stale', refresh: 'r1');
      var calls = 0;
      var refreshCalls = 0;
      final client = _client(
        MockClient((request) async {
          if (request.url.path.endsWith('auth/token/refresh/')) {
            refreshCalls += 1;
            expect(jsonDecode(request.body)['refresh'], 'r1');
            return http.Response(
              jsonEncode({'access': 'fresh', 'refresh': 'r2'}),
              200,
            );
          }
          calls += 1;
          if (calls == 1) return http.Response('', 401);
          expect(request.headers['Authorization'], 'Bearer fresh');
          return http.Response(jsonEncode({'count': 1, 'results': []}), 200);
        }),
        tokens,
      );
      final data = await client.getJson('procedures/');
      expect(calls, 2, reason: 'the replay must hit the endpoint again');
      expect(refreshCalls, 1);
      expect(tokens.refreshApplied, 1);
      expect(tokens.access, 'fresh');
      expect(data, {'count': 1, 'results': []});
    });

    test('parallel 401 requests share a single refresh', () async {
      final tokens = FakeTokens(access: 'stale', refresh: 'r1');
      var refreshCalls = 0;
      final client = _client(
        MockClient((request) async {
          if (request.url.path.endsWith('auth/token/refresh/')) {
            refreshCalls += 1;
            await Future<void>.delayed(const Duration(milliseconds: 20));
            return http.Response(
              jsonEncode({'access': 'fresh', 'refresh': 'r2'}),
              200,
            );
          }
          if (request.headers['Authorization'] == 'Bearer fresh') {
            return http.Response(jsonEncode({'ok': true}), 200);
          }
          return http.Response('', 401);
        }),
        tokens,
      );
      final results = await Future.wait(
        [client.getJson('procedures/'), client.getJson('procedures/?x=1')],
      );
      expect(refreshCalls, 1, reason: 'single-flight refresh');
      expect(results, everyElement({'ok': true}));
    });

    test('permanent 401 raises a session expiry with the error body', () async {
      final tokens = FakeTokens(access: 'stale', refresh: null);
      final client = _client(
        MockClient((request) async => http.Response(
              jsonEncode({
                'error': {
                  'code': 'invalid_token',
                  'message': 'Token rejected.',
                },
              }),
              401,
            )),
        tokens,
      );
      try {
        await client.getJson('procedures/');
        fail('should have thrown');
      } on ApiException catch (error) {
        expect(error.status, 401);
        expect(error.code, 'invalid_token');
        expect(error.friendlyMessage, 'Token rejected.');
      }
      expect(tokens.expiredCallbacks, 1);
    });

    test('error envelope surfaces field details', () async {
      final tokens = FakeTokens(access: 'abc', refresh: null);
      final client = _client(
        MockClient((request) async => http.Response(
              jsonEncode({
                'error': {
                  'code': 'validation_error',
                  'message': 'Check the values.',
                  'details': {'file': 'Too large.'},
                },
              }),
              400,
            )),
        tokens,
      );
      try {
        await client.postJson('procedures/', body: {'x': 1});
        fail('should have thrown');
      } on ApiException catch (error) {
        expect(error.details?['file'], 'Too large.');
      }
    });
  });
}
