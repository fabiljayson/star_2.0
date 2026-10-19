import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_session.dart';

import '../../core/api_client.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'marketplace_repository.dart';
import 'product.dart';

/// Shipping form, then one order per supplier is created.
class CheckoutPage extends StatefulWidget {
  const CheckoutPage({super.key});

  @override
  State<CheckoutPage> createState() => _CheckoutPageState();
}

class _CheckoutPageState extends State<CheckoutPage> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _addressController = TextEditingController();
  final _phoneController = TextEditingController();
  late final MarketplaceRepository _repo;
  bool _placing = false;
  String? _error;
  List<Order>? _created;

  @override
  void initState() {
    super.initState();
    _repo = MarketplaceRepository(context.read<AppSession>());
    final user = context.read<AppSession>().user;
    _nameController.text = user?.fullName ?? '';
  }

  @override
  void dispose() {
    _nameController.dispose();
    _addressController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _placeOrder() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _placing = true;
      _error = null;
    });
    try {
      final orders = await _repo.checkout(
        name: _nameController.text.trim(),
        address: _addressController.text.trim(),
        phone: _phoneController.text.trim(),
      );
      if (!mounted) return;
      setState(() => _created = orders);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.friendlyMessage);
    } finally {
      if (mounted) setState(() => _placing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final created = _created;
    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: created != null
          ? ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const EmptyView(
                  icon: Icons.task_alt,
                  title: 'Order(s) placed',
                  subtitle: 'They now wait for payment. Open the orders tab.',
                ),
                for (final order in created) ...[
                  const SizedBox(height: 8),
                  StarGlass(
                    child: Text('${order.reference} · ${order.total} ${order.currency}'),
                  ),
                ],
              ],
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('Shipping details', style: theme.textTheme.titleMedium),
                const SizedBox(height: 8),
                Form(
                  key: _formKey,
                  child: Column(
                    children: [
                      TextFormField(
                        controller: _nameController,
                        decoration: const InputDecoration(
                          labelText: 'Recipient name',
                        ),
                        validator: (value) =>
                            value == null || value.trim().isEmpty
                                ? 'Enter a contact name.'
                                : null,
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _addressController,
                        decoration: const InputDecoration(
                          labelText: 'Shipping address',
                        ),
                        validator: (value) =>
                            value == null || value.trim().isEmpty
                                ? 'Enter a shipping address.'
                                : null,
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _phoneController,
                        decoration: const InputDecoration(
                          labelText: 'Phone number',
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                if (_error != null) ErrorNotice(message: _error!),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: _placing ? null : _placeOrder,
                  child: _placing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Place order(s)'),
                ),
                const SizedBox(height: 8),
                Text(
                  'One order is created per supplier. Payment happens on the '
                  'order screen once placed.',
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: StarColors.textInverseMuted),
                ),
              ],
            ),
    );
  }
}
