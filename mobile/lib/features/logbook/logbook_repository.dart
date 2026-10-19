import '../../core/api_client.dart';
import '../../core/app_session.dart';
import 'procedure.dart';

/// Data access for the surgical logbook (subset used by the mobile MVP).
class LogbookRepository {
  LogbookRepository(this.session);

  final AppSession session;

  ApiClient get _client => session.api;

  Future<List<Procedure>> list({
    bool mineOnly = false,
    String? status,
    int pageSize = 20,
  }) async {
    // The list endpoint returns DRF-style {"count": n, "results": [...]}.
    final data = await _client.getJson('procedures/', query: {
      'page_size': '$pageSize',
      if (mineOnly) 'mine': '1',
      if (status != null && status.isNotEmpty) 'status': status,
    });
    return _parseList(data);
  }

  List<Procedure> _parseList(dynamic data) {
    if (data is! Map<String, dynamic>) return const [];
    final raw = data['results'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(Procedure.fromJson)
        .toList();
  }

  Future<Procedure> get(String id) async =>
      Procedure.fromJson(_m(await _client.getJson('procedures/$id/')));

  Future<Procedure> create(ProcedureCreateInput input) async =>
      Procedure.fromJson(
        _m(await _client.postJson('procedures/', body: input.toJson())),
      );

  Future<Procedure> submit(String id) async => Procedure.fromJson(
        _m(await _client.postJson('procedures/$id/submit/')),
      );

  Future<Procedure> saveDraftNote({
    required String id,
    required String summary,
    required int version,
  }) async =>
      Procedure.fromJson(_m(
        await _client.patchJson('procedures/$id/', {
          'summary': summary,
          'version': version,
        }),
      ));

  static Map<String, dynamic> _m(dynamic value) => (value as Map).cast<String, dynamic>();
}
