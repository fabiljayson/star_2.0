import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'cart_page.dart';
import 'marketplace_repository.dart';
import 'product.dart';
import 'subscription_page.dart';
import 'product_detail_page.dart';

/// Catalog + cart entry point (buyer experience).
class MarketplacePage extends StatefulWidget {
  const MarketplacePage({super.key});

  @override
  State<MarketplacePage> createState() => _MarketplacePageState();
}

class _MarketplacePageState extends State<MarketplacePage> {
  late final MarketplaceRepository _repo;
  String? _categorySlug;

  @override
  void initState() {
    super.initState();
    _repo = MarketplaceRepository(context.read<AppSession>());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Marketplace'),
        actions: _supplierMarketplaceActions(context),
      ),
      body: Column(
        children: [
          _CategoryBar(
            repository: _repo,
            selected: _categorySlug,
            onSelected: (slug) => setState(() => _categorySlug = slug),
          ),
          Expanded(
            child: _ProductList(
              repository: _repo,
              categorySlug: _categorySlug,
            ),
          ),
        ],
      ),
    );
  }

  /// Suppliers get an entry to the seller subscription screen — the paywall
  /// for selling rights is enforced by the server, this is only a shortcut.
  List<Widget> _supplierMarketplaceActions(BuildContext context) {
    final session = context.read<AppSession>();
    final user = session.user;
    final isSupplier =
        user != null && user.roleNames.contains('supplier');
    return [
      if (isSupplier)
        IconButton(
          tooltip: 'Seller plan',
          icon: const Icon(Icons.storefront_outlined),
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SubscriptionPage()),
            );
          },
        ),
      IconButton(
        tooltip: 'Cart',
        icon: const Icon(Icons.shopping_cart_outlined),
        onPressed: () {
          Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const CartPage()),
          );
        },
      ),
    ];
  }
}

/// Horizontally scrolling category chips (with an "All" chip first).
class _CategoryBar extends StatefulWidget {
  const _CategoryBar({
    required this.repository,
    required this.selected,
    required this.onSelected,
  });

  final MarketplaceRepository repository;
  final String? selected;
  final ValueChanged<String?> onSelected;

  @override
  State<_CategoryBar> createState() => _CategoryBarState();
}

class _CategoryBarState extends State<_CategoryBar> {
  List<ProductCategory>? _categories;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final items = await widget.repository.categories();
      if (mounted) setState(() => _categories = items);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.friendlyMessage);
    }
  }

  @override
  Widget build(BuildContext context) {
    final categories = _categories;
    if (_error != null) {
      return Padding(padding: const EdgeInsets.all(12), child: ErrorNotice(message: _error!));
    }
    if (categories == null) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: LinearProgressIndicator(minHeight: 2),
      );
    }
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        children: [
          _chip(
            label: 'All',
            slug: '',
            selected: widget.selected == null,
            onSelect: () => widget.onSelected(null),
          ),
          for (final category in categories)
            _chip(
              label: category.name,
              slug: category.slug,
              selected: widget.selected == category.slug,
              onSelect: () => widget.onSelected(category.slug),
            ),
        ],
      ),
    );
  }

  Widget _chip({
    required String label,
    required String slug,
    required bool selected,
    required VoidCallback onSelect,
  }) =>
      Padding(
        padding: const EdgeInsets.only(right: 8),
        child: ChoiceChip(
          label: Text(label),
          selected: selected,
          visualDensity: VisualDensity.compact,
          onSelected: (_) => onSelect(),
        ),
      );
}

/// Product list, refreshed when the selected category changes.
class _ProductList extends StatefulWidget {
  const _ProductList({required this.repository, required this.categorySlug});

  final MarketplaceRepository repository;
  final String? categorySlug;

  @override
  State<_ProductList> createState() => _ProductListState();
}

class _ProductListState extends State<_ProductList> {
  List<Product>? _products;
  String? _error;
  String? _loadedForSlug;

  @override
  void didUpdateWidget(covariant _ProductList oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.categorySlug != widget.categorySlug) _load();
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final slug = widget.categorySlug;
    setState(() {
      _error = null;
      _products = null;
    });
    try {
      final items =
          await widget.repository.products(categorySlug: slug);
      if (mounted && slug == widget.categorySlug) {
        setState(() {
          _products = items;
          _loadedForSlug = slug;
        });
      }
    } on ApiException catch (error) {
      if (mounted && slug == widget.categorySlug) {
        setState(() => _error = error.friendlyMessage);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    assert(_loadedForSlug != null || _error != null || _products == null);
    final products = _products;
    if (_error != null) {
      return ErrorView(message: _error!, onRetry: _load);
    }
    if (products == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (products.isEmpty) {
      return const EmptyView(
        icon: Icons.inventory_2_outlined,
        title: 'No products',
        subtitle: 'Nothing published in this category yet.',
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        itemCount: products.length,
        separatorBuilder: (_, _) => const SizedBox(height: 8),
        itemBuilder: (context, index) => _ProductTile(product: products[index]),
      ),
    );
  }
}

class _ProductTile extends StatelessWidget {
  const _ProductTile({required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final quantity = product.freeQuantity;
    return InkWell(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute<void>(builder: (_) => ProductDetailPage(product: product)),
        );
      },
      child: StarGlass(
        child: Row(
          children: [
            Container(
              decoration: BoxDecoration(
                color: StarColors.primarySoft,
                borderRadius: BorderRadius.circular(StarColors.radiusMd),
              ),
              padding: const EdgeInsets.all(10),
              child: const Icon(Icons.medical_services_outlined,
                  color: StarColors.primary),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(product.name,
                      style: theme.textTheme.bodyLarge
                          ?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 2),
                  Text(
                    '${product.supplierName} · ${product.categoryName}',
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: StarColors.textInverseMuted),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${_money(product.unitPrice)} ${product.currency}',
                  style: theme.textTheme.labelLarge
                      ?.copyWith(color: StarColors.primary),
                ),
                Text(
                  quantity > 0 ? '$quantity in stock' : 'Out of stock',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: quantity > 0
                        ? StarColors.textInverseMuted
                        : StarColors.danger,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _money(String amount) => amount.toString().trim();
}
