import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_session.dart';

import '../../core/api_client.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'marketplace_repository.dart';
import 'product.dart';

/// Product detail with add-to-cart quantity selector.
class ProductDetailPage extends StatefulWidget {
  const ProductDetailPage({super.key, required this.product});

  final Product product;

  @override
  State<ProductDetailPage> createState() => _ProductDetailPageState();
}

class _ProductDetailPageState extends State<ProductDetailPage> {
  late final MarketplaceRepository _repo;
  late Product _product;
  int _quantity = 1;
  bool _adding = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _product = widget.product;
    _repo = MarketplaceRepository(context.read<AppSession>());
  }

  Future<void> _refresh() async {
    try {
      final product = await _repo.product(_product.id);
      if (mounted) setState(() => _product = product);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.friendlyMessage);
    }
  }

  Future<void> _addToCart() async {
    FocusScope.of(context).unfocus();
    if (_product.freeQuantity <= 0) return;
    setState(() {
      _adding = true;
      _error = null;
    });
    try {
      await _repo
          .addToCart(productId: _product.id, quantity: _quantity);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Added to cart.'),
            behavior: SnackBarBehavior.floating,
          ),
        );
        Navigator.of(context).pop();
      }
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.friendlyMessage);
      }
    } finally {
      if (mounted) setState(() => _adding = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final product = _product;
    return Scaffold(
      appBar: AppBar(title: Text(product.name)),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            StarGlass(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(product.name,
                      style: theme.textTheme.headlineSmall
                          ?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 6),
                  Text(
                    '${product.supplierName} · ${product.categoryName} · ${product.sku}',
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: StarColors.textInverseMuted),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    '${_format(product.unitPrice)} ${product.currency}',
                    style: theme.textTheme.headlineMedium
                        ?.copyWith(color: StarColors.primary, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    product.freeQuantity > 0
                        ? '${product.freeQuantity} available'
                        : 'Out of stock',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: product.freeQuantity > 0
                          ? StarColors.textInverseMuted
                          : StarColors.danger,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            if (product.description.isNotEmpty)
              StarGlass(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Description', style: theme.textTheme.titleSmall),
                    const SizedBox(height: 6),
                    Text(product.description, style: theme.textTheme.bodyMedium),
                  ],
                ),
              ),
            const SizedBox(height: 12),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: ErrorNotice(message: _error!),
              ),
            Row(
              children: [
                const Spacer(),
                IconButton(
                  onPressed: (_adding || _quantity <= 1)
                      ? null
                      : () => setState(() => _quantity -= 1),
                  icon: const Icon(Icons.remove_circle_outline),
                ),
                Text('$_quantity',
                    style: theme.textTheme.titleMedium),
                IconButton(
                  onPressed:
                      (_adding || _quantity >= product.freeQuantity)
                          ? null
                          : () => setState(() => _quantity += 1),
                  icon: const Icon(Icons.add_circle_outline),
                ),
                const Spacer(),
              ],
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: (_adding || product.freeQuantity <= 0) ? null : _addToCart,
              child: _adding
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(
                      product.freeQuantity > 0 ? 'Add to cart' : 'Not available',
                    ),
            ),
          ],
        ),
      ),
    );
  }

  String _format(String amount) => amount;
}
