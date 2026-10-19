import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'checkout_page.dart';
import 'marketplace_repository.dart';
import 'product.dart';

/// Cart contents with quantity editing and checkout entry.
class CartPage extends StatefulWidget {
  const CartPage({super.key});

  @override
  State<CartPage> createState() => _CartPageState();
}

class _CartPageState extends State<CartPage> {
  late final MarketplaceRepository _repo;
  List<CartItem>? _items;
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
      final items = await _repo.cart();
      if (mounted) setState(() => _items = items);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.friendlyMessage);
    }
  }

  Future<void> _changeQuantity(CartItem item, int quantity) async {
    try {
      await _repo.updateCartItem(id: item.id, quantity: quantity);
      await _reload();
    } on ApiException catch (error) {
      _failBar(error.friendlyMessage);
    }
  }

  Future<void> _removeItem(CartItem item) async {
    try {
      await _repo.removeCartItem(item.id);
      await _reload();
    } on ApiException catch (error) {
      _failBar(error.friendlyMessage);
    }
  }

  void _failBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }

  String get _total {
    final items = _items;
    if (items == null) return '';
    int grand = 0;
    for (final item in items) {
      grand += int.tryParse(item.lineTotal) ?? 0;
    }
    final currency = items.isEmpty ? 'XOF' : items.first.currency;
    return '$grand $currency';
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return Scaffold(
      appBar: AppBar(title: const Text('Cart')),
      body: items == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_error != null) ...[
                  ErrorNotice(message: _error!),
                  const SizedBox(height: 8),
                ],
                if (items.isEmpty) ...[
                  const SizedBox(height: 32),
                  const EmptyView(
                    icon: Icons.shopping_cart_outlined,
                    title: 'Your cart is empty',
                    subtitle: 'Add products from the marketplace.',
                  ),
                ],
                for (final item in items) ...[
                  _CartTile(
                    item: item,
                    onChangedQuantity: (value) => _changeQuantity(item, value),
                    onRemove: () => _removeItem(item),
                  ),
                  const SizedBox(height: 8),
                ],
                if (items.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Text('Total: $_total',
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium
                              ?.copyWith(fontWeight: FontWeight.bold)),
                      const Spacer(),
                      FilledButton(
                        onPressed: () async {
                          FocusScope.of(context).unfocus();
                          await Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => const CheckoutPage(),
                            ),
                          );
                          if (mounted) await _reload();
                        },
                        child: Text('Checkout · $items order(s)'),
                      ),
                    ],
                  ),
                ],
              ],
            ),
    );
  }
}

class _CartTile extends StatelessWidget {
  const _CartTile({
    required this.item,
    required this.onChangedQuantity,
    required this.onRemove,
  });

  final CartItem item;
  final ValueChanged<int> onChangedQuantity;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return StarGlass(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(item.productName,
                        style: theme.textTheme.bodyLarge
                            ?.copyWith(fontWeight: FontWeight.bold)),
                    Text(
                      '${item.productSku} · ${_lineItemLabel(item)}',
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: StarColors.textInverseMuted),
                    ),
                  ],
                ),
              ),
              IconButton(
                onPressed: onRemove,
                tooltip: 'Remove from cart',
                icon: const Icon(Icons.delete_outline,
                    color: StarColors.danger),
              ),
            ],
          ),
          Row(
            children: [
              IconButton(
                onPressed: item.quantity <= 1
                    ? null
                    : () => onChangedQuantity(item.quantity - 1),
                icon: const Icon(Icons.remove_circle_outline),
              ),
              Text('${item.quantity}'),
              IconButton(
                onPressed: () => onChangedQuantity(item.quantity + 1),
                icon: const Icon(Icons.add_circle_outline),
              ),
              const Spacer(),
              Text(
                '${item.lineTotal} ${item.currency}',
                style: theme.textTheme.labelLarge
                    ?.copyWith(color: StarColors.primary),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _lineItemLabel(CartItem item) => 'each ${item.unitPrice} ${item.currency}';
}
