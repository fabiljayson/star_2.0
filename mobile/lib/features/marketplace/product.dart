/// Buyer-side marketplace models (mirrors web/src/lib/types.ts subset).
class ProductCategory {
  const ProductCategory({required this.id, required this.name, required this.slug});

  final String id;
  final String name;
  final String slug;

  factory ProductCategory.fromJson(Map<String, dynamic> json) =>
      ProductCategory(
        id: '${json['id']}',
        name: (json['name'] ?? '') as String,
        slug: (json['slug'] ?? '') as String,
      );
}

class Product {
  Product({
    required this.id,
    required this.supplierName,
    required this.categorySlug,
    required this.categoryName,
    required this.name,
    required this.description,
    required this.sku,
    this.imageUrl = '',
    this.imageCredit = '',
    required this.unitPrice,
    required this.currency,
    required this.freeQuantity,
  });

  final String id;
  final String supplierName;
  final String categorySlug;
  final String categoryName;
  final String name;
  final String description;
  final String sku;
  final String imageUrl;
  final String imageCredit;
  /// Amounts come as strings from the DRF API ("2500"), XOF has no decimals.
  final String unitPrice;
  final String currency;
  final int freeQuantity;

  factory Product.fromJson(Map<String, dynamic> json) => Product(
        id: '${json['id']}',
        supplierName: (json['supplier_name'] ?? '') as String,
        categorySlug: (json['category'] ?? '').toString(),
        categoryName: (json['category_name'] ?? '') as String,
        name: (json['name'] ?? '') as String,
        description: (json['description'] ?? '').toString(),
        sku: (json['sku'] ?? '') as String,
        imageUrl: (json['image_url'] ?? '').toString(),
        imageCredit: (json['image_credit'] ?? '').toString(),
        unitPrice: (json['unit_price'] ?? '0').toString(),
        currency: (json['currency'] ?? 'XOF') as String,
        freeQuantity:
            int.tryParse('${json['free_quantity'] ?? 0}') ?? 0,
      );
}

class CartItem {
  CartItem({
    required this.id,
    required this.productId,
    required this.productName,
    required this.productSku,
    required this.quantity,
    required this.unitPrice,
    required this.currency,
    required this.lineTotal,
  });

  final String id;
  final String productId;
  final String productName;
  final String productSku;
  final int quantity;
  final String unitPrice;
  final String currency;
  final String lineTotal;

  factory CartItem.fromJson(Map<String, dynamic> json) {
    final product = json['product_detail'] is Map<String, dynamic>
        ? json['product_detail'] as Map<String, dynamic>
        : const <String, dynamic>{};
    return CartItem(
      id: '${json['id']}',
      productId: '${json['product'] ?? product['id'] ?? ''}',
      productName: (product['name'] ?? '') as String,
      productSku: (product['sku'] ?? '') as String,
      quantity: int.tryParse('${json['quantity'] ?? 0}') ?? 0,
      unitPrice: (product['unit_price'] ?? '0').toString(),
      currency: (product['currency'] ?? 'XOF').toString(),
      lineTotal: (json['line_total'] ?? '0').toString(),
    );
  }
}

class OrderItem {
  const OrderItem({
    required this.id,
    required this.productName,
    required this.productSku,
    required this.quantity,
    required this.unitPrice,
    required this.lineTotal,
  });

  final String id;
  final String productName;
  final String productSku;
  final int quantity;
  final String unitPrice;
  final String lineTotal;

  factory OrderItem.fromJson(Map<String, dynamic> json) => OrderItem(
        id: '${json['id']}',
        productName: (json['product_name'] ?? '') as String,
        productSku: (json['product_sku'] ?? '') as String,
        quantity: int.tryParse('${json['quantity'] ?? 0}') ?? 0,
        unitPrice: (json['unit_price'] ?? '0').toString(),
        lineTotal: (json['line_total'] ?? '0').toString(),
      );
}

class Payment {
  Payment({
    required this.id,
    required this.status,
    required this.amount,
    required this.currency,
    required this.provider,
    this.paidAt,
    this.failureReason,
  });

  final String id;
  final String status;
  final String amount;
  final String currency;
  final String provider;
  final String? paidAt;
  final String? failureReason;

  factory Payment.fromJson(Map<String, dynamic> json) => Payment(
        id: '${json['id']}',
        status: '${json['status'] ?? ''}',
        amount: (json['amount'] ?? '0').toString(),
        currency: (json['currency'] ?? 'XOF') as String,
        provider: (json['provider'] ?? '') as String,
        paidAt: json['paid_at']?.toString(),
        failureReason: json['failure_reason']?.toString(),
      );
}

class Shipment {
  const Shipment({required this.status, this.trackingNumber});

  final String status;
  final String? trackingNumber;

  factory Shipment.fromJson(Map<String, dynamic> json) => Shipment(
        status: '${json['status'] ?? ''}',
        trackingNumber: json['tracking_number']?.toString(),
      );
}

class Order {
  Order({
    required this.id,
    required this.reference,
    required this.status,
    required this.currency,
    required this.subtotal,
    required this.total,
    required this.items,
    required this.payments,
    required this.supplierName,
    required this.placedAt,
    required this.shippingAddress,
    this.shipment,
  });

  final String id;
  final String reference;
  final String status;
  final String currency;
  final String subtotal;
  final String total;
  final List<OrderItem> items;
  final List<Payment> payments;
  final String supplierName;
  final String placedAt;
  final String shippingAddress;
  final Shipment? shipment;

  factory Order.fromJson(Map<String, dynamic> json) => Order(
        id: '${json['id']}',
        reference: '${json['reference'] ?? ''}',
        status: '${json['status'] ?? ''}',
        currency: (json['currency'] ?? 'XOF') as String,
        subtotal: (json['subtotal'] ?? '0').toString(),
        total: (json['total'] ?? '0').toString(),
        items: _list(json['items']).map(OrderItem.fromJson).toList(),
        payments: _list(json['payments']).map(Payment.fromJson).toList(),
        supplierName: (json['supplier_name'] ?? '') as String,
        placedAt: '${json['placed_at'] ?? ''}',
        shippingAddress: (json['shipping_address'] ?? '') as String,
        shipment: json['shipment'] is Map<String, dynamic>
            ? Shipment.fromJson(json['shipment'] as Map<String, dynamic>)
            : null,
      );

  /// The most recent payment is what the UI surfaces first.
  Payment? get latestPendingPayment {
    for (final payment in payments) {
      if (payment.status == 'pending') return payment;
    }
    return null;
  }
}

List<Map<String, dynamic>> _list(dynamic value) {
  if (value is! List) return const [];
  return value.whereType<Map<String, dynamic>>().toList();
}
