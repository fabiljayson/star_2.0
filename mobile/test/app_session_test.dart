import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:star_mobile/core/api_client.dart';
import 'package:star_mobile/core/app_session.dart';
import 'package:star_mobile/core/session_store.dart';

const _defaultUser = {
  'id': '11111111-1111-1111-1111-111111111111',
  'email': 'dr@example.test',
  'full_name': 'Dr Demo',
  'is_verified': true,
  'is_platform_admin': false,
  'roles': <Map<String, dynamic>>[],
};

AppSession _sessionWithHandler(
  SessionStore store,
  Future<http.Response> Function(http.Request request) handler,
) {
  final session = AppSession(
    store: store,
    clientFactory: (tokens) => ApiClient(
      baseUrl: 'http://test.local/api/v1',
      tokens: tokens,
      httpClient: MockClient(handler),
    ),
  );
  return session;
}

void main() {
  test('direct login stores the session and flips phase', () async {
    final store = SessionStore(storage: MemorySecureStore());
    final session = _sessionWithHandler(
      store,
      (request) async {
        if (request.url.path.endsWith('auth/login/')) {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['email'], 'dr@example.test');
          expect(body['password'], 'Secret-1');
          return http.Response(
            jsonEncode({
              'mfa_required': false,
              'access': 'acc1',
              'refresh': 'ref1',
              'user': _defaultUser,
            }),
            200,
          );
        }
        return http.Response('', 404);
      },
    );
    await session.restore();
    expect(session.phase, AuthPhase.signedOut);

    await session.login('dr@example.test', 'Secret-1');
    expect(session.phase, AuthPhase.signedIn);
    expect(session.user?.email, 'dr@example.test');
    expect(session.user?.fullName, 'Dr Demo');

    final persisted = await store.load();
    expect(persisted?.accessToken, 'acc1');
    expect(persisted?.refreshToken, 'ref1');
  });

  test('MFA login requires the second step before tokens land', () async {
    final store = SessionStore(storage: MemorySecureStore());
    var loginCalls = 0;
    final session = _sessionWithHandler(
      store,
      (request) async {
        if (request.url.path.endsWith('auth/login/')) {
          loginCalls += 1;
          return http.Response(
            jsonEncode({
              'mfa_required': true,
              'mfa_token': 'mfa-challenge',
              'expires_in': 120,
            }),
            200,
          );
        }
        if (request.url.path.endsWith('auth/mfa/verify/')) {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['mfa_token'], 'mfa-challenge');
          expect(body['code'], '123456');
          return http.Response(
            jsonEncode({
              'mfa_required': false,
              'access': 'acc2',
              'refresh': 'ref2',
              'user': _defaultUser,
            }),
            200,
          );
        }
        return http.Response('', 404);
      },
    );
    await session.restore();

    await session.login('dr@example.test', 'Secret-1');
    expect(loginCalls, 1);
    expect(session.phase, AuthPhase.requiresMfa);
    expect(await store.load(), isNull, reason: 'nothing stored before MFA');

    await session.verifyMfa(' 123456 ');
    expect(session.phase, AuthPhase.signedIn);
    expect((await store.load())?.accessToken, 'acc2');
  });

  test('cancelMfa returns to the sign-in form', () async {
    final store = SessionStore(storage: MemorySecureStore());
    final session = _sessionWithHandler(
      store,
      (request) async => http.Response(
        jsonEncode({
          'mfa_required': true,
          'mfa_token': 'mfa-challenge',
          'expires_in': 120,
        }),
        200,
      ),
    );
    await session.restore();
    await session.login('dr@example.test', 'Secret-1');
    expect(session.phase, AuthPhase.requiresMfa);

    session.cancelMfa();
    expect(session.phase, AuthPhase.signedOut);
  });

  test('restore drops a revoked session (me + refresh both 401)', () async {
    final store = SessionStore(storage: MemorySecureStore());
    await store.save(StoredSession(
      accessToken: 'dead',
      refreshToken: 'dead2',
      user: _defaultUser,
    ));
    final session = _sessionWithHandler(
      store,
      (request) async {
        if (request.url.path.endsWith('users/me/')) {
          return http.Response('', 401);
        }
        if (request.url.path.endsWith('auth/token/refresh/')) {
          return http.Response(jsonEncode({'detail': 'expired'}), 401);
        }
        return http.Response('', 500);
      },
    );
    await session.restore();
    // sessionExpired() runs in a microtask; drain it before asserting.
    await Future<void>.delayed(Duration.zero);
    expect(session.phase, AuthPhase.signedOut);
    expect(await store.load(), isNull);
    expect(session.user, isNull);
  });

  test('restore keeps the session when the server is unreachable', () async {
    final store = SessionStore(storage: MemorySecureStore());
    await store.save(StoredSession(
      accessToken: 'dead',
      refreshToken: 'dead2',
      user: _defaultUser,
    ));
    final session = _sessionWithHandler(
      store,
      (request) async => throw Exception('no network'),
    );
    await session.restore();
    expect(session.phase, AuthPhase.signedOut);
    expect(await store.load(), isNotNull, reason: 'offline: keep local data');
  });

  test('onboarding completion persists across sessions', () async {
    final store = SessionStore(storage: MemorySecureStore());
    final session = _sessionWithHandler(
      store,
      (request) async => http.Response('', 404),
    );
    expect(session.onboardingDone, isTrue, reason: 'default before restore');
    await session.restore();
    expect(session.onboardingDone, isFalse, reason: 'fresh install');

    await session.completeOnboarding();
    expect(session.onboardingDone, isTrue);
    expect(await store.isOnboardingDone(), isTrue);

    final reloaded = AppSession(
      store: store,
      clientFactory: (tokens) => ApiClient(
        baseUrl: 'http://test.local/api/v1',
        tokens: tokens,
        httpClient: MockClient((request) async => http.Response('', 404)),
      ),
    );
    await reloaded.restore();
    expect(reloaded.onboardingDone, isTrue);
  });

  test('logout clears the local session even if the server is offline',
      () async {
    final store = SessionStore(storage: MemorySecureStore());
    await store.save(StoredSession(
      accessToken: 'a',
      refreshToken: 'r',
      user: _defaultUser,
    ));
    final session = _sessionWithHandler(
      store,
      (request) async => throw Exception('no network'),
    );
    await session.restore();
    // (Unreachable server above means phase flips to signed-out; simulate a
    // signed-in call by pushing phase manually through the same path.)
    expect(session.phase, AuthPhase.signedOut);

    await session.logout();
    expect(session.phase, AuthPhase.signedOut);
    expect(await store.load(), isNull);
  });

  test('updateServerUrl resets the session to sign-in', () async {
    final store = SessionStore(storage: MemorySecureStore());
    final session = _sessionWithHandler(
      store,
      (request) async => http.Response(
        jsonEncode({
          'mfa_required': false,
          'access': 'acc1',
          'refresh': 'ref1',
          'user': _defaultUser,
        }),
        200,
      ),
    );
    await session.restore();
    await session.login('dr@example.test', 'Secret-1');
    expect(session.phase, AuthPhase.signedIn);

    await session.updateServerUrl(' http://other.local/api/v1/');
    expect(session.serverUrl, 'http://other.local/api/v1');
    expect(session.phase, AuthPhase.signedOut);
    expect(await store.load(), isNull);
    expect(
      await store.loadServerUrl(),
      'http://other.local/api/v1',
      reason: 'the server choice itself is persisted',
    );
  });
}
