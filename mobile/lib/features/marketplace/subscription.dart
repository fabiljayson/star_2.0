/// Seller subscription models (mirrors backend web/src/lib/types.ts payload).
class SubscriptionPlanOption {
  const SubscriptionPlanOption({
    required this.plan,
    required this.priceFcfa,
    required this.durationMonths,
  });

  final String plan;
  final int priceFcfa;
  final int durationMonths;

  factory SubscriptionPlanOption.fromJson(Map<String, dynamic> json) =>
      SubscriptionPlanOption(
        plan: '${json['plan'] ?? ''}',
        priceFcfa: int.tryParse('${json['price_fcfa'] ?? 0}') ?? 0,
        durationMonths: int.tryParse('${json['duration_months'] ?? 0}') ?? 0,
      );

  String get label => switch (plan) {
        'monthly' => 'Monthly',
        'semiannual' => 'Semi-annual',
        'annual' => 'Annual',
        _ => plan.isEmpty ? 'Plan' : plan,
      };
}

class SubscriptionStatus {
  const SubscriptionStatus({
    required this.status,
    required this.plan,
    required this.amountFcfa,
    required this.currency,
    required this.canPublish,
    required this.plans,
    this.startsAt,
    this.expiresAt,
  });

  final String status;
  final String? plan;
  final int amountFcfa;
  final String currency;
  /// Selling rights are governed by the server; this mirrors the payload.
  final bool canPublish;
  final List<SubscriptionPlanOption> plans;
  final String? startsAt;
  final String? expiresAt;

  factory SubscriptionStatus.fromJson(Map<String, dynamic> json) =>
      SubscriptionStatus(
        status: '${json['status'] ?? 'none'}',
        plan: _nullable(json['plan']),
        amountFcfa: int.tryParse('${json['amount_fcfa'] ?? 0}') ?? 0,
        currency: (json['currency'] ?? 'XOF').toString(),
        canPublish: json['can_publish'] == true,
        plans: _list(json['plans']).map(SubscriptionPlanOption.fromJson).toList(),
        startsAt: _nullable(json['starts_at']),
        expiresAt: _nullable(json['expires_at']),
      );
}

/// Checkout / polled payment for a subscription (SubscriptionPaymentSerializer).
class SubscriptionPayment {
  const SubscriptionPayment({
    required this.id,
    required this.status,
    required this.amount,
    required this.currency,
    required this.provider,
    this.failureReason,
  });

  final String id;
  final String status;
  final String amount;
  final String currency;
  final String provider;
  final String? failureReason;

  factory SubscriptionPayment.fromJson(Map<String, dynamic> json) =>
      SubscriptionPayment(
        id: '${json['id']}',
        status: '${json['status'] ?? ''}',
        amount: (json['amount'] ?? '0').toString(),
        currency: (json['currency'] ?? 'XOF').toString(),
        provider: (json['provider'] ?? '').toString(),
        failureReason: json['failure_reason']?.toString(),
      );
}

List<Map<String, dynamic>> _list(dynamic value) {
  if (value is! List) return const [];
  return value.whereType<Map<String, dynamic>>().toList();
}

String? _nullable(dynamic value) {
  if (value == null) return null;
  final text = '$value';
  return text.isEmpty ? null : text;
}
