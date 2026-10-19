import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'marketplace_repository.dart';
import 'order_detail_page.dart';
import 'product.dart';

/// Buyer order history.
class OrdersPage extends StatefulWidget {
  const OrdersPage({super.key});

  @override
  State<OrdersPage> createState() => _OrdersPageState();
}

class _OrdersPageState extends State<OrdersPage> {
  late final MarketplaceRepository _repo;
  List<Order>? _orders;
  String? _error;

  @override
  void initState() {
    super.initState();
    _repo = MarketplaceRepository(context.read<AppSession>());
    _reload();
  }

  Future<void> _reload() async {
    setState(() => _error = null);
    try {
      final orders = await _repo.orders();
      if (mounted) setState(() => _orders = orders);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.friendlyMessage);
    }
  }

  @override
  Widget build(BuildContext context) {
    final orders = _orders;
    return RefreshIndicator(
      onRefresh: _reload,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          if (_error != null) ...[
            ErrorNotice(message: _error!),
            const SizedBox(height: 8),
            TextButton(onPressed: _reload, child: const Text('Retry')),
          ] else if (orders == null) ...[
            const SizedBox(height: 40),
            const Center(child: CircularProgressIndicator()),
          ] else if (orders.isEmpty) ...[
            const SizedBox(height: 24),
            const EmptyView(
              icon: Icons.receipt_long_outlined,
              title: 'No orders yet',
              subtitle: 'Orders you place will appear here.',
            ),
          ] else
            for (final order in orders) ...[
              const SizedBox(height: 8),
              _OrderTile(order: order),
            ],
        ],
      ),
    );
  }
}

class _OrderTile extends StatelessWidget {
  const _OrderTile({required this.order});

  final Order order;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => OrderDetailPage(orderId: order.id),
          ),
        );
      },
      child: StarGlass(
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(order.reference,
                          style: theme.textTheme.bodyLarge
                              ?.copyWith(fontWeight: FontWeight.bold)),
                      Text(
                        '${order.supplierName} · ${order.placedAt.substring(0, order.placedAt.length.clamp(0, 10))}',
                        style: theme.textTheme.bodySmall
                            ?.copyWith(color: StarColors.textInverseMuted),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    StatusBadge(status: order.status),
                    const SizedBox(height: 4),
                    Text('${order.total} ${order.currency}'),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
