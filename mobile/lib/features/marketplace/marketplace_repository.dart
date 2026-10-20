import '../../core/api_client.dart';
import '../../core/app_session.dart';
import 'product.dart';
import 'subscription.dart';

/// Buyer-side marketplace data access.
class MarketplaceRepository {
  MarketplaceRepository(this.session);

  final AppSession session;

  ApiClient get _client => session.api;

  Future<List<ProductCategory>> categories() async {
    final data = await _client.getJson('marketplace/categories/');
    if (data is! List) return const [];
    return data
        .whereType<Map<String, dynamic>>()
        .map(ProductCategory.fromJson)
        .toList();
  }

  Future<List<Product>> products({String? categorySlug, String? search}) async {
    final data = await _client.getJson('marketplace/products/', query: {
      'page_size': '50',
      if (categorySlug != null && categorySlug.isNotEmpty)
        'category': categorySlug,
      if (search != null && search.isNotEmpty) 'q': search,
    });
    return _results(data).map(Product.fromJson).toList();
  }

  Future<Product> product(String id) async =>
      Product.fromJson(_m(await _client.getJson('marketplace/products/$id/')));

  // ── Cart ─────────────────────────────────────────────────────────────
  Future<List<CartItem>> cart() async {
    final data = await _client.getJson('marketplace/cart/');
    return _results(data).map(CartItem.fromJson).toList();
  }

  Future<CartItem> addToCart({
    required String productId,
    required int quantity,
  }) async =>
      CartItem.fromJson(_m(await _client.postJson('marketplace/cart/items/', body: {
        'product': productId,
        'quantity': quantity,
      })));

  Future<CartItem> updateCartItem({required String id, required int quantity}) =>
      _client.patchJson('marketplace/cart/items/$id/', {'quantity': quantity})
          .then((value) => CartItem.fromJson(_m(value)));

  Future<void> removeCartItem(String id) => _client.deleteJson(
      'marketplace/cart/items/$id/');

  // ── Checkout / orders ────────────────────────────────────────────────
  /// Returns the orders created (one per supplier).
  Future<List<Order>> checkout({
    required String name,
    required String address,
    required String phone,
  }) async {
    final data = await _client.postJson('marketplace/checkout/', body: {
      'shipping': {'name': name, 'address': address, 'phone': phone},
    });
    if (data is! List) return const [];
    return data
        .whereType<Map<String, dynamic>>()
        .map(Order.fromJson)
        .toList();
  }

  Future<List<Order>> orders() async {
    final data = await _client.getJson('marketplace/orders/', query: {
      'page_size': '50',
    });
    return _results(data).map(Order.fromJson).toList();
  }

  Future<Order> order(String id) async =>
      Order.fromJson(_m(await _client.getJson('marketplace/orders/$id/')));

  Future<Order> cancelOrder(String id, String reason) async =>
      Order.fromJson(_m(await _client.postJson('marketplace/orders/$id/cancel/', body: {
        'reason': reason,
      })));

  /// Sandbox payment: returns the fresh payment (status pending) to simulate.
  Future<Payment> pay(String orderId, String idempotencyKey) async {
    // The server reads Idempotency-Key from the header or from the body;
    // our client has no header hook, so use the body alias.
    final payload = _m(await _client.postJson(
      'marketplace/orders/$orderId/pay/',
      body: {'idempotency_key': idempotencyKey},
    ));
    return Payment.fromJson(payload);
  }

  Future<Payment> simulate(String paymentId, bool succeeded) async =>
      Payment.fromJson(_m(await _client.postJson(
        'marketplace/payments/$paymentId/simulate/',
        body: {'outcome': succeeded ? 'succeeded' : 'failed'},
      )));

  Future<Payment> payment(String id) async =>
      Payment.fromJson(_m(await _client.getJson('marketplace/payments/$id/')));

  // ── Seller subscription ──────────────────────────────────────────────
  Future<SubscriptionStatus> subscriptionStatus() async => SubscriptionStatus
      .fromJson(_m(await _client.getJson('marketplace/subscription/')));

  /// Starts a subscription checkout; returns the pending payment to wait for.
  Future<SubscriptionPayment> subscriptionCheckout(String plan) async =>
      SubscriptionPayment.fromJson(_m(await _client.postJson(
        'marketplace/subscription/checkout/',
        body: {'plan': plan},
      )));

  /// Owner-only route: subscription payments are invisible to everyone else.
  Future<SubscriptionPayment> subscriptionPayment(String id) async =>
      SubscriptionPayment.fromJson(
        _m(await _client.getJson('marketplace/subscription/payments/$id/')),
      );

  Future<Order> requestRefund(String orderId, String reason) async =>
      Order.fromJson(_m(
        await _client.postJson('marketplace/orders/$orderId/refund-request/', body: {
          'reason': reason,
        }),
      ));

  // ── Low level ────────────────────────────────────────────────────────
  List<Map<String, dynamic>> _results(dynamic data) {
    if (data is List) return data.whereType<Map<String, dynamic>>().toList();
    if (data is! Map<String, dynamic>) return const [];
    final raw = data['results'];
    if (raw is! List) return const [];
    return raw.whereType<Map<String, dynamic>>().toList();
  }

  static Map<String, dynamic> _m(dynamic value) =>
      (value as Map).cast<String, dynamic>();
}
