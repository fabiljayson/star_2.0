import '../../core/api_client.dart';
import '../../core/app_session.dart';
import 'legal_models.dart';

/// Data access for the Policies & Legal Center.
///
/// Every request goes through the shared [ApiClient] so authentication,
/// refresh and error envelopes behave exactly like the rest of the app.
class LegalRepository {
  LegalRepository(this.session);

  final AppSession session;

  ApiClient get _client => session.api;

  final Map<String, PolicyDetail> _cache = {};

  /// Last successfully downloaded copy, if any. Lets screens keep showing
  /// text (clearly labelled as cached) when the network drops.
  PolicyDetail? cachedPolicy(String slug, String language) =>
      _cache['$slug:$language'];

  Future<List<PolicySummary>> policies(String language) async {
    final data = await _client.getJson(
      'legal/policies/',
      query: {'lang': language},
    );
    return _results(data).map(PolicySummary.fromJson).toList();
  }

  Future<PolicyDetail> policy(String slug, String language) async {
    final detail = PolicyDetail.fromJson(_map(
      await _client.getJson('legal/policies/$slug/', query: {'lang': language}),
    ));
    _cache['$slug:$language'] = detail;
    return detail;
  }

  Future<List<PolicyHistoryItem>> history(String slug, String language) async {
    final data = await _client.getJson(
      'legal/policies/$slug/versions/',
      query: {'lang': language},
    );
    return _results(data).map(PolicyHistoryItem.fromJson).toList();
  }

  Future<List<ConsentStatusItem>> consentStatus() async {
    final data = await _client.getJson('legal/consents/status/');
    return _results(data).map(ConsentStatusItem.fromJson).toList();
  }

  Future<List<ConsentRecord>> consentHistory() async {
    final data = await _client.getJson(
      'legal/consents/mine/',
      query: {'page_size': '50'},
    );
    return _results(data).map(ConsentRecord.fromJson).toList();
  }

  Future<void> accept({
    required String policySlug,
    required String version,
    required String language,
    String context = 'account',
  }) async {
    await _client.postJson('legal/consents/', body: {
      'policy_slug': policySlug,
      'version': version,
      'language': language,
      'context': context,
    });
  }

  Future<bool> withdraw(String policySlug) async {
    final data = await _client.postJson('legal/consents/withdraw/', body: {
      'policy': policySlug,
    });
    final map = _map(data);
    return map['consent_id'] != null;
  }

  Future<List<PrivacyRequestItem>> privacyRequests() async {
    final data = await _client.getJson(
      'legal/privacy-requests/mine/',
      query: {'page_size': '50'},
    );
    return _results(data).map(PrivacyRequestItem.fromJson).toList();
  }

  Future<PrivacyRequestItem> openPrivacyRequest({
    required String kind,
    required String message,
  }) async =>
      PrivacyRequestItem.fromJson(_map(await _client.postJson(
        'legal/privacy-requests/',
        body: {'kind': kind, 'message': message},
      )));

  static List<Map<String, dynamic>> _results(dynamic data) {
    final list = data is Map ? data['results'] : data;
    if (list is! List) return const [];
    return list.whereType<Map<String, dynamic>>().toList();
  }

  static Map<String, dynamic> _map(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    return (value as Map).cast<String, dynamic>();
  }
}
