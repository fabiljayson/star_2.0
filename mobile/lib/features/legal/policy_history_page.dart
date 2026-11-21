import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'legal_models.dart';
import 'legal_repository.dart';
import 'legal_strings.dart';

/// Immutable published history for one policy in the selected language.
class PolicyHistoryPage extends StatefulWidget {
  const PolicyHistoryPage({
    super.key,
    required this.repository,
    required this.slug,
    required this.language,
  });

  final LegalRepository repository;
  final String slug;
  final String language;

  @override
  State<PolicyHistoryPage> createState() => _PolicyHistoryPageState();
}

class _PolicyHistoryPageState extends State<PolicyHistoryPage> {
  List<PolicyHistoryItem>? _items;
  Object? _error;

  LegalStrings get _t => LegalStrings.forLanguage(widget.language);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final items = await widget.repository.history(widget.slug, widget.language);
      if (!mounted) return;
      setState(() => _items = items);
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_t.history)),
      body: _body(),
    );
  }

  Widget _body() {
    if (_error != null && _items == null) {
      return ErrorView(
        message: _error is ApiException
            ? (_error as ApiException).friendlyMessage
            : _t.loadFailed,
        onRetry: _load,
      );
    }
    final items = _items;
    if (items == null) return const Center(child: CircularProgressIndicator());
    if (items.isEmpty) {
      return EmptyView(icon: Icons.history, title: _t.notPublished);
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final item = items[index];
        final current = index == 0;
        return Card(
          child: ListTile(
            leading: CircleAvatar(
              radius: 18,
              backgroundColor: (current ? StarColors.primary : StarColors.glassRim)
                  .withValues(alpha: 0.22),
              child: Text(
                item.version,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: current ? StarColors.primary : StarColors.textInverse,
                ),
              ),
            ),
            title: Text('${_t.version} ${item.version}'),
            subtitle: Text(
              [
                statusLabel(item.status),
                if (item.effectiveDate != null)
                  '${_t.effective} '
                      '${formatLegalDate(item.effectiveDate, widget.language)}',
                if (item.publishedAt != null)
                  '${_t.published} '
                      '${formatLegalDate(item.publishedAt, widget.language)}',
              ].join(' · '),
            ),
            trailing: current
                ? const Icon(Icons.check_circle, color: StarColors.primary)
                : null,
          ),
        );
      },
    );
  }
}
