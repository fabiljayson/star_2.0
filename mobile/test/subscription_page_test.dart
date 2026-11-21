import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:star_mobile/core/api_client.dart';
import 'package:star_mobile/core/app_session.dart';
import 'package:star_mobile/core/session_store.dart';
import 'package:star_mobile/features/marketplace/subscription_page.dart';

const _statusActive = {
  'status': 'active',
  'plan': 'monthly',
  'amount_fcfa': 5000,
  'currency': 'XOF',
  'starts_at': '2026-10-01T00:00:00Z',
  'expires_at': '2029-01-01T00:00:00Z',
  'can_publish': true,
  'plans': [
    {'plan': 'monthly', 'price_fcfa': 5000, 'duration_months': 1},
    {'plan': 'annual', 'price_fcfa': 12000, 'duration_months': 12},
  ],
};

const _paymentPending = {
  'id': 'pay-1',
  'provider': 'sandbox',
  'status': 'pending',
  'amount': '5000',
  'currency': 'XOF',
  'failure_reason': null,
};

AppSession _session(
  Future<http.Response> Function(http.Request request) handler, {
  bool isAdmin = false,
}) {
  final session = AppSession(
    store: SessionStore(storage: MemorySecureStore()),
    clientFactory: (tokens) => ApiClient(
      baseUrl: 'http://test.local/api/v1',
      tokens: tokens,
      httpClient: MockClient(handler),
    ),
  );
  session.user = StarUser(
    id: 'u-1',
    email: 'supplier@example.test',
    fullName: 'Demo Supplier',
    isVerified: true,
    isPlatformAdmin: isAdmin,
    roles: const <Map<String, dynamic>>[],
  );
  return session;
}

Future<http.Response> _ok(Object payload) async => http.Response(
      jsonEncode(payload),
      200,
      headers: {'Content-Type': 'application/json'},
    );

void main() {
  testWidgets('shows the active status and lets sellers start a checkout',
      (tester) async {
    var pollCount = 0;
    final session = _session(
      (request) async {
        final path = request.url.path;
        if (path.endsWith('marketplace/subscription/')) return _ok(_statusActive);
        if (path.endsWith('marketplace/subscription/checkout/')) {
          return _ok(_paymentPending);
        }
        if (path.endsWith('marketplace/subscription/payments/pay-1/')) {
          pollCount += 1;
          return _ok(
            pollCount == 1
                ? _paymentPending
                : {..._paymentPending, 'status': 'succeeded'},
          );
        }
        return http.Response('{}', 404);
      },
    );

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: session,
        child: const MaterialApp(home: SubscriptionPage()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Subscribe').first);
    await tester.pumpAndSettle();

    expect(find.textContaining('Checkout started'), findsOneWidget);

    // Trigger the 2.5 s polling timer; the first poll still returns the
    // pending payment, the second one carries the server verdict.
    await tester.pump(const Duration(milliseconds: 2500));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 2500));
    await tester.pumpAndSettle();
    expect(find.textContaining('Payment confirmed'), findsOneWidget);
  });

  testWidgets('failed payments never grant selling rights', (tester) async {
    final session = _session(
      (request) async {
        final path = request.url.path;
        if (path.endsWith('marketplace/subscription/')) {
          return _ok({..._statusActive, 'status': 'none', 'plan': null});
        }
        if (path.endsWith('marketplace/subscription/checkout/')) {
          return http.Response(jsonEncode(_paymentPending), 201);
        }
        if (path.endsWith('marketplace/subscription/payments/pay-1/')) {
          return _ok({
            ..._paymentPending,
            'status': 'failed',
            'failure_reason': 'sandbox_declined',
          });
        }
        return http.Response('{}', 404);
      },
    );

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: session,
        child: const MaterialApp(home: SubscriptionPage()),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Subscribe').first);
    await tester.pump(const Duration(milliseconds: 2500));
    await tester.pumpAndSettle();

    expect(find.textContaining('Payment rejected'), findsOneWidget);
    expect(find.textContaining('sandbox_declined'), findsOneWidget);
    expect(find.textContaining('never granted'), findsNothing);
  });
}
