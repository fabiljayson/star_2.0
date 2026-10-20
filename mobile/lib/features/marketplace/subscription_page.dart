import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'marketplace_repository.dart';
import 'subscription.dart';

enum CheckoutPhase { idle, pending, succeeded, failed }

/// Seller subscription screen: server-driven plans, live countdown and payment
/// polling. Selling rights come only from the server's verified payment.
class SubscriptionPage extends StatefulWidget {
  const SubscriptionPage({super.key});

  @override
  State<SubscriptionPage> createState() => _SubscriptionPageState();
}

class _SubscriptionPageState extends State<SubscriptionPage> {
  late final MarketplaceRepository _repo;
  bool _isAdmin = false;

  SubscriptionStatus? _status;
  String? _error;

  CheckoutPhase _phase = CheckoutPhase.idle;
  String? _message;
  SubscriptionPayment? _checkout;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _repo = MarketplaceRepository(context.read<AppSession>());
    _isAdmin = context.read<AppSession>().user?.isPlatformAdmin ?? false;
    _reload();
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  // ── Actions ───────────────────────────────────────────────────────────
  Future<void> _reload() async {
    setState(() => _error = null);
    try {
      final status = await _repo.subscriptionStatus();
      if (mounted) setState(() => _status = status);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.friendlyMessage);
    }
  }

  Future<void> _startCheckout(String plan) async {
    setState(() {
      _phase = CheckoutPhase.pending;
      _message = 'Starting checkout…';
    });
    try {
      final payment = await _repo.subscriptionCheckout(plan);
      if (!mounted) return;
      setState(() {
        _checkout = payment;
        _message = 'Checkout started. Finish the payment with your provider; '
            'the STAR server confirms the outcome before granting any '
            'selling right.';
      });
      _startPolling();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _phase = CheckoutPhase.failed;
          _message = error.friendlyMessage;
        });
      }
    }
  }

  void _startPolling() {
    _poll?.cancel();
    _poll = Timer.periodic(
      const Duration(milliseconds: 2500),
      (_) => _pollCheckout(),
    );
  }

  // Poll the owner-only subscription payment endpoint until the server has a
  // verdict. Connectivity hiccups keep the loop alive.
  Future<void> _pollCheckout() async {
    final payment = _checkout;
    if (payment == null) return;
    try {
      final fresh = await _repo.subscriptionPayment(payment.id);
      if (fresh.status == payment.status) return;
      _stopPolling();
      if (!mounted) return;
      setState(() {
        _checkout = null;
        switch (fresh.status) {
          case 'succeeded':
            _phase = CheckoutPhase.succeeded;
            _message = 'Payment confirmed. Your seller subscription is active.';
          case 'failed':
            _phase = CheckoutPhase.failed;
            _message =
                'Payment rejected: ${fresh.failureReason ?? 'declined by provider'}. '
                'No selling right was granted.';
          default:
            _phase = CheckoutPhase.failed;
            _message = 'Checkout cancelled. No payment was confirmed.';
        }
      });
      await _reload();
    } on ApiException {
      // Keep polling on transient errors.
    }
  }

  void _stopPolling() {
    _poll?.cancel();
    _poll = null;
    _checkout = null;
  }

  Future<void> _simulate(bool succeeded) async {
    final payment = _checkout;
    if (payment == null) return;
    try {
      final updated = await _repo.simulate(payment.id, succeeded);
      if (mounted) {
        setState(() {
          _checkout = payment.withStatus(updated.status, updated.failureReason);
        });
      }
      await _pollCheckout();
    } on ApiException catch (error) {
      if (mounted) setState(() => _message = error.friendlyMessage);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = _status;

    return Scaffold(
      appBar: AppBar(title: const Text('Seller plan')),
      body: status == null && _error == null
          ? const Center(
              child: CircularProgressIndicator(color: StarColors.primary),
            )
          : RefreshIndicator(
              color: StarColors.primary,
              onRefresh: _reload,
              child: ListView(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                children: [
                  if (_error != null) ...[
                    ErrorNotice(message: _error!),
                    const SizedBox(height: 12),
                  ],
                  if (status != null) ...[
                    _StatusCard(status: status),
                    const SizedBox(height: 12),
                    if (status.plans.isNotEmpty)
                      StarGlass(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Plans',
                                style: theme.textTheme.titleMedium),
                            const SizedBox(height: 4),
                            Text(
                              'Amounts are in FCFA. The first monthly plan '
                              'starts at 2 500 FCFA for a seller\'s very '
                              'first month. Renewal keeps unused time.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: StarColors.textInverseMuted,
                              ),
                            ),
                            for (final plan in status.plans) ...[
                              const SizedBox(height: 8),
                              Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(plan.label,
                                            style: theme.textTheme.bodyLarge),
                                        Text(
                                          '${grouped(plan.priceFcfa)} FCFA · '
                                          '${plan.durationMonths} month(s)',
                                          style: theme.textTheme.bodySmall
                                              ?.copyWith(
                                                  color: StarColors
                                                      .textInverseMuted),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  FilledButton(
                                    onPressed:
                                        _phase == CheckoutPhase.pending
                                            ? null
                                            : () => _startCheckout(plan.plan),
                                    child: Text(
                                      status.status == 'active' &&
                                              plan.plan == status.plan
                                          ? 'Renew this plan'
                                          : 'Subscribe',
                                    ),
                                  ),
                                ],
                              ),
                            ],
                            const SizedBox(height: 6),
                            Text(
                              'No auto-renewal: a subscription never renews '
                              'without an explicit payment.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: StarColors.textInverseMuted,
                              ),
                            ),
                          ],
                        ),
                      ),
                    const SizedBox(height: 12),
                  ],
                  _CheckoutPanel(
                    phase: _phase,
                    message: _message,
                    payment: _checkout,
                    isAdmin: _isAdmin,
                    onSimulate: _simulate,
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
    );
  }
}

extension _PaymentCopy on SubscriptionPayment {
  SubscriptionPayment withStatus(String status, String? failureReason) =>
      SubscriptionPayment(
        id: id,
        status: status,
        amount: amount,
        currency: currency,
        provider: provider,
        failureReason: failureReason,
      );
}

// ── Status card ──────────────────────────────────────────────────────────
class _StatusCard extends StatefulWidget {
  const _StatusCard({required this.status});

  final SubscriptionStatus status;

  @override
  State<_StatusCard> createState() => _StatusCardState();
}

class _StatusCardState extends State<_StatusCard> {
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    _startTicker();
  }

  @override
  void didUpdateWidget(covariant _StatusCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    _startTicker();
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  void _startTicker() {
    _ticker?.cancel();
    if (widget.status.status == 'active' && _expiresAt != null) {
      _ticker = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (!mounted) {
          timer.cancel();
          return;
        }
        setState(() {});
      });
    }
  }

  DateTime? get _expiresAt =>
      DateTime.tryParse(widget.status.expiresAt ?? '');

  String get countdown {
    final expiresAt = _expiresAt;
    if (expiresAt == null) return '—';
    var seconds = expiresAt.difference(DateTime.now()).inSeconds;
    if (seconds < 0) seconds = 0;
    final days = seconds ~/ 86400;
    final hours = (seconds % 86400) ~/ 3600;
    final minutes = (seconds % 3600) ~/ 60;
    final secs = seconds % 60;
    return '$days d '
        '${hours.toString().padLeft(2, '0')}:'
        '${minutes.toString().padLeft(2, '0')}:'
        '${secs.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = widget.status;

    final badge = switch (status.status) {
      'active' => StatusBadge(status: 'active'),
      'pending' => StatusBadge(status: 'pending'),
      'expired' || 'cancelled' => StatusBadge(status: 'expired'),
      'failed' => StatusBadge(status: 'failed'),
      _ => StatusBadge(status: 'none'),
    };

    final (title, explanation) = switch (status.status) {
      'active' => (
          planTitle(status),
          'Your listings stay visible while the subscription is active. '
              'Expires ${status.expiresAt} · remaining $countdown.'
        ),
      'pending' => (
          'Checkout in progress',
          'A payment is waiting for confirmation. Nothing is granted before '
              'the server verifies it.'
        ),
      'failed' => (
          'Last payment failed',
          'The last attempt did not succeed. You can start a new checkout at '
              'any time — you are not locked out.'
        ),
      'expired' => (
          'Expired',
          'Your listings no longer sell; renewing restores access. '
              'Expired on ${status.expiresAt}.'
        ),
      'cancelled' => (
          'Cancelled',
          'This plan was cancelled before confirmation. Start a new checkout '
              'whenever you like.'
        ),
      _ => (
          'No subscription yet',
          'Selling on STAR Marketplace requires an active plan. Choose one '
              'below.'
        ),
    };

    return StarGlass(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          badge,
          const SizedBox(height: 8),
          Text(title, style: theme.textTheme.bodyLarge),
          const SizedBox(height: 4),
          Text(
            explanation,
            style: theme.textTheme.bodySmall
                ?.copyWith(color: StarColors.textInverseMuted),
          ),
        ],
      ),
    );
  }

  static String planTitle(SubscriptionStatus status) {
    if (status.plan == null) return 'Active subscription';
    final amount = grouped(status.amountFcfa);
    return 'Active plan ${status.plan}. $amount FCFA';
  }
}

// ── Checkout / sandbox panel ─────────────────────────────────────────────
class _CheckoutPanel extends StatelessWidget {
  const _CheckoutPanel({
    required this.phase,
    required this.message,
    required this.payment,
    required this.isAdmin,
    required this.onSimulate,
  });

  final CheckoutPhase phase;
  final String? message;
  final SubscriptionPayment? payment;
  final bool isAdmin;
  final ValueChanged<bool> onSimulate;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (message == null) return const SizedBox.shrink();

    final success = phase == CheckoutPhase.succeeded;
    final awaiting = payment != null && phase == CheckoutPhase.pending;
    return StarGlass(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                success ? Icons.check_circle : Icons.info_outline,
                size: 18,
                color: success
                    ? StarColors.success
                    : phase == CheckoutPhase.failed
                        ? StarColors.danger
                        : StarColors.warning,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(message!, style: theme.textTheme.bodyMedium),
              ),
            ],
          ),
          if (awaiting && isAdmin) ...[
            const SizedBox(height: 8),
            Text(
              'Sandbox provider: the buttons below simulate the provider',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: StarColors.textInverseMuted),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                OutlinedButton(
                  onPressed: () => onSimulate(true),
                  child: const Text('Confirm success'),
                ),
                const SizedBox(width: 12),
                OutlinedButton(
                  onPressed: () => onSimulate(false),
                  child: const Text('Trigger failure'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// Very simple thousands separator, e.g. 5000 → "5 000" (FCFA style).
String grouped(int value) =>
    value.toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]} ');
