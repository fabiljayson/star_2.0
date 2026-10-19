import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:star_mobile/core/api_client.dart';
import 'package:star_mobile/core/app_session.dart';
import 'package:star_mobile/core/session_store.dart';
import 'package:star_mobile/features/auth/login_page.dart';
import 'package:star_mobile/features/auth/mfa_page.dart';
import 'package:star_mobile/home_shell.dart';

const _user = {
  'id': '11111111-1111-1111-1111-111111111111',
  'email': 'dr@example.test',
  'full_name': 'Dr Demo',
  'is_verified': true,
  'is_platform_admin': false,
  'roles': <Map<String, dynamic>>[],
};

Future<void> _pump(WidgetTester tester, AppSession session) async {
  await session.restore();
  await tester.pumpWidget(
    ChangeNotifierProvider<AppSession>.value(
      value: session,
      child: const MaterialApp(home: AuthGate()),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _fillCredentials(
  WidgetTester tester, {
  String email = 'dr@example.test',
  String password = 'Secret-1',
}) async {
  await tester.enterText(
      find.widgetWithText(TextFormField, 'Email'), email);
  await tester.enterText(
      find.widgetWithText(TextFormField, 'Password'), password);
  await tester.pump();
}

void main() {
  testWidgets('successful sign-in lands on the dashboard', (tester) async {
    final store = SessionStore(storage: MemorySecureStore());
    final session = AppSession(
      store: store,
      clientFactory: (tokens) => ApiClient(
        baseUrl: 'http://test.local/api/v1',
        tokens: tokens,
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('auth/login/')) {
            return http.Response(
              jsonEncode({
                'mfa_required': false,
                'access': 'acc1',
                'refresh': 'ref1',
                'user': _user,
              }),
              200,
            );
          }
          if (request.url.path.endsWith('notifications/unread-count/')) {
            return http.Response(jsonEncode({'unread': 0}), 200);
          }
          return http.Response(
            jsonEncode({'count': 0, 'results': []}),
            200,
          );
        }),
      ),
    );
    await _pump(tester, session);
    expect(session.phase, AuthPhase.signedOut);
    expect(find.byType(LoginPage), findsOneWidget);

    await _fillCredentials(tester);
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();

    expect(session.phase, AuthPhase.signedIn);
    expect((await store.load())?.accessToken, 'acc1');
    expect(find.byType(MfaPage), findsNothing);
  });

  testWidgets('MFA challenge lands on the code screen', (tester) async {
    final session = AppSession(
      store: SessionStore(storage: MemorySecureStore()),
      clientFactory: (tokens) => ApiClient(
        baseUrl: 'http://test.local/api/v1',
        tokens: tokens,
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('auth/login/')) {
            return http.Response(
              jsonEncode({
                'mfa_required': true,
                'mfa_token': 'challenge-1',
                'expires_in': 120,
              }),
              200,
            );
          }
          return http.Response(
            jsonEncode({
              'mfa_required': false,
              'access': 'acc2',
              'refresh': 'ref2',
              'user': _user,
            }),
            200,
          );
        }),
      ),
    );
    await _pump(tester, session);

    await _fillCredentials(tester);
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();

    expect(session.phase, AuthPhase.requiresMfa);
    expect(find.byType(MfaPage), findsOneWidget);

    // Completing MFA stores the pair and reaches the shell.
    await tester.enterText(
        find.widgetWithText(TextFormField, 'Code'), ' 123456 ');
    await tester.tap(find.text('Verify'));
    await tester.pumpAndSettle();
    expect(session.phase, AuthPhase.signedIn);
  });

  testWidgets('wrong password surfaces an inline error notice',
      (tester) async {
    final session = AppSession(
      store: SessionStore(storage: MemorySecureStore()),
      clientFactory: (tokens) => ApiClient(
        baseUrl: 'http://test.local/api/v1',
        tokens: tokens,
        httpClient: MockClient((request) async => http.Response(
              jsonEncode({
                'error': {
                  'code': 'invalid_credentials',
                  'message': 'Wrong email or password.',
                },
              }),
              401,
            )),
      ),
    );
    await _pump(tester, session);
    await _fillCredentials(tester);
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();

    expect(session.phase, AuthPhase.signedOut);
    expect(find.byType(LoginPage), findsOneWidget);
    expect(find.text('Wrong email or password.'), findsOneWidget);
  });

  testWidgets('empty form shows the validators, no network call',
      (tester) async {
    var calls = 0;
    final session = AppSession(
      store: SessionStore(storage: MemorySecureStore()),
      clientFactory: (tokens) => ApiClient(
        baseUrl: 'http://test.local/api/v1',
        tokens: tokens,
        httpClient: MockClient((request) async {
          calls += 1;
          return http.Response('[]', 200);
        }),
      ),
    );
    await _pump(tester, session);

    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();

    expect(calls, 0);
    expect(find.text('Enter your email.'), findsOneWidget);
    expect(find.text('Enter your password.'), findsOneWidget);
  });

  testWidgets('custom server URL is applied at submit time', (tester) async {
    final store = SessionStore(storage: MemorySecureStore());
    final session = AppSession(
      store: store,
      clientFactory: (tokens) => ApiClient(
        baseUrl: 'http://test.local/api/v1',
        tokens: tokens,
        httpClient: MockClient((request) async => http.Response(
              jsonEncode({
                'error': {'code': 'stopped_in_mock', 'message': 'Stopped by the test mock.'},
              }),
              401,
            )),
      ),
    );
    await _pump(tester, session);

    await tester.tap(find.text('Other server…'));
    await tester.pumpAndSettle();
    await _fillCredentials(tester);
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Server URL'),
      'http://new.local/api/v1/',
    );
    // Only applied when pressing Sign in (kept before that).
    expect(session.serverUrl, isNot('http://new.local/api/v1'));

    await tester.ensureVisible(find.text('Sign in'));
    await tester.pump();
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();

    expect(session.serverUrl, 'http://new.local/api/v1');
    expect(await store.loadServerUrl(), 'http://new.local/api/v1');
  });
}
