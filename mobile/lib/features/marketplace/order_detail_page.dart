import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'marketplace_repository.dart';
import 'product.dart';

/// Full order screen: items, shipments, payments and buyer actions.
class OrderDetailPage extends StatefulWidget {
  const OrderDetailPage({super.key, required this.orderId});

  final String orderId;

  @override
  State<OrderDetailPage> createState() => _OrderDetailPageState();
}

class _OrderDetailPageState extends State<OrderDetailPage> {
  late final MarketplaceRepository _repo;
  Order? _order;
  String? _error;
  bool _working = false;

  @override
  void initState() {
    super.initState();
    _repo = MarketplaceRepository(context.read<AppSession>());
    _reload();
  }

  Future<void> _reload() async {
    setState(() => _error = null);
    try {
      final order = await _repo.order(widget.orderId);
      if (mounted) setState(() => _order = order);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.friendlyMessage);
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _working = true;
      _error = null;
    });
    try {
      await action();
      await _reload();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.friendlyMessage);
      }
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final order = _order;
    final theme = Theme.of(context);
    final isAdmin = context.read<AppSession>().user?.isPlatformAdmin ?? false;
    return Scaffold(
      appBar: AppBar(title: Text(order?.reference ?? 'Order')),
      body: order == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _reload,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
                children: [
                  if (_error != null) ...[
                    ErrorNotice(message: _error!),
                    const SizedBox(height: 8),
                  ],
                  StarGlass(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment:
                              MainAxisAlignment.spaceBetween,
                          children: [
                            Flexible(child: StatusBadge(status: order.status)),
                            Text(
                              '${order.total} ${order.currency}',
                              style: theme.textTheme.titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text('Supplier: ${order.supplierName}',
                            style: theme.textTheme.bodyMedium),
                        if (order.shippingAddress.isNotEmpty)
                          Text('Ship to: ${order.shippingAddress}',
                              style: theme.textTheme.bodySmall?.copyWith(
                                  color: StarColors.textInverseMuted)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text('Items', style: theme.textTheme.titleMedium),
                  const SizedBox(height: 4),
                  for (final item in order.items) ...[
                    const SizedBox(height: 8),
                    StarGlass(
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(item.productName,
                                    style: theme.textTheme.bodyLarge),
                                Text(
                                  '${item.productSku} · ${item.quantity} × ${item.unitPrice} ${order.currency}',
                                  style: theme.textTheme.bodySmall?.copyWith(
                                      color: StarColors.textInverseMuted),
                                ),
                              ],
                            ),
                          ),
                          Text('${item.lineTotal} ${order.currency}'),
                        ],
                      ),
                    ),
                  ],
                  if (order.shipment != null) ...[
                    const SizedBox(height: 16),
                    Text('Shipment', style: theme.textTheme.titleMedium),
                    const SizedBox(height: 8),
                    StarGlass(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: StatusBadge(
                                    status: order.shipment!.status),
                              ),
                              Text(
                                order.shipment!.trackingNumber == null
                                    ? ''
                                    : 'Tracking: ${order.shipment!.trackingNumber!}',
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  Text('Payments', style: theme.textTheme.titleMedium),
                  const SizedBox(height: 4),
                  for (final payment in order.payments) ...[
                    const SizedBox(height: 8),
                    StarGlass(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: StatusBadge(status: payment.status),
                              ),
                              Text('${payment.amount} ${payment.currency}'),
                            ],
                          ),
                          if (payment.failureReason != null)
                            Text(
                              payment.failureReason!,
                              style: theme.textTheme.bodySmall
                                  ?.copyWith(color: StarColors.danger),
                            ),
                          if (_working) const LinearProgressIndicator(),
                        ],
                      ),
                    ),
                    if (payment.status == 'pending' && order.status == 'pending_payment') ...[
                      const SizedBox(height: 4),
                      Text(
                        'Sandbox payments: the buttons below simulate the provider.',
                        style: theme.textTheme.bodySmall
                            ?.copyWith(color: StarColors.textInverseMuted),
                      ),
                      if (isAdmin) ...[
                        TextButton(
                          onPressed: _working
                              ? null
                              : () => _run(
                                    () => _repo.simulate(payment.id, true),
                                  ),
                          child: const Text('Sandbox: payment succeeded'),
                        ),
                        TextButton(
                          onPressed: _working
                              ? null
                              : () => _run(
                                    () => _repo.simulate(payment.id, false),
                                  ),
                          child: const Text('Sandbox: payment failed'),
                        ),
                      ],
                    ],
                  ],
                  const SizedBox(height: 16),
                  if (order.status == 'pending_payment')
                    FilledButton(
                      onPressed:
                          _working ? null : () => _run(() => _pay(order)),
                      child: _working
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text('Pay ${order.total} ${order.currency}'),
                    ),
                  if (order.status == 'pending_payment')
                    TextButton(
                      onPressed: _working
                          ? null
                          : () => _run(() => _cancel(order)),
                      child: const Text('Cancel order'),
                    ),
                  if (order.status == 'paid' || order.status == 'delivered')
                    TextButton(
                      onPressed: _working
                          ? null
                          : () => _run(() => _requestRefund(order)),
                      child: const Text('Request refund'),
                    ),
                ],
              ),
            ),
    );
  }

  Future<void> _pay(Order order) async =>
      _repo.pay(order.id, 'mob-${DateTime.now().millisecondsSinceEpoch}');

  Future<void> _cancel(Order order) async {
    final reason = await _askReason('Cancel order', 'Tell the supplier why:');
    if (reason == null) return;
    await _repo.cancelOrder(order.id, reason);
  }

  Future<void> _requestRefund(Order order) async {
    final reason = await _askReason('Refund request', 'Why should the supplier refund it?');
    if (reason == null) return;
    await _repo.requestRefund(order.id, reason);
  }

  Future<String?> _askReason(String title, String hint) =>
      showDialog<String>(
        context: context,
        builder: (dialogContext) {
          final controller = TextEditingController();
          return AlertDialog(
            title: Text(title),
            content: TextField(
              controller: controller,
              autofocus: true,
              decoration: InputDecoration(hintText: hint),
            ),
            actions: [
              TextButton(
                onPressed: () =>
                    Navigator.of(dialogContext).pop(),
                child: const Text('Keep order'),
              ),
              FilledButton(
                onPressed: () =>
                    Navigator.of(dialogContext).pop(controller.text.trim()),
                child: const Text('Continue'),
              ),
            ],
          );
        },
      );
}
