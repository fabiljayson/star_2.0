import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'legal_models.dart';
import 'legal_repository.dart';
import 'legal_strings.dart';

/// Current consent state plus the full consent trail for the account.
class ConsentsPage extends StatefulWidget {
  const ConsentsPage({
    super.key,
    required this.repository,
    required this.language,
  });

  final LegalRepository repository;
  final String language;

  @override
  State<ConsentsPage> createState() => _ConsentsPageState();
}

class _ConsentsPageState extends State<ConsentsPage> {
  List<ConsentStatusItem>? _status;
  List<ConsentRecord>? _history;
  Object? _error;
  String? _busyPolicy;

  LegalStrings get _t => LegalStrings.forLanguage(widget.language);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final status = await widget.repository.consentStatus();
      final history = await widget.repository.consentHistory();
      if (!mounted) return;
      setState(() {
        _status = status;
        _history = history;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error);
    }
  }

  Future<void> _accept(ConsentStatusItem item) async {
    setState(() => _busyPolicy = item.policy);
    try {
      await widget.repository.accept(
        policySlug: item.policy,
        version: item.currentVersion,
        language: widget.language,
      );
      await _load();
    } catch (error) {
      if (mounted) showError(context, error);
    } finally {
      if (mounted) setState(() => _busyPolicy = null);
    }
  }

  Future<void> _withdraw(ConsentStatusItem item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(_t.withdraw),
        content: Text('${item.title} — ${_t.withdraw.toLowerCase()}?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(MaterialLocalizations.of(context).cancelButtonLabel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(_t.withdraw),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _busyPolicy = item.policy);
    try {
      final changed = await widget.repository.withdraw(item.policy);
      if (!mounted) return;
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(
          content: Text(changed ? _t.withdrawn : _t.noConsents),
        ));
    } catch (error) {
      if (mounted) showError(context, error);
    } finally {
      if (mounted) setState(() => _busyPolicy = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    final history = _history;
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(_t.consents),
          bottom: TabBar(
            tabs: [
              Tab(text: _t.consents),
              Tab(text: _t.consentHistory),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _currentTab(status),
            _historyTab(history),
          ],
        ),
      ),
    );
  }

  Widget _currentTab(List<ConsentStatusItem>? status) {
    if (_error != null && status == null) {
      return ErrorView(
        message: _error is ApiException
            ? (_error as ApiException).friendlyMessage
            : _t.loadFailed,
        onRetry: _load,
      );
    }
    if (status == null) return const Center(child: CircularProgressIndicator());
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final item in status)
            Card(
              child: ListTile(
                title: Text(item.title),
                subtitle: Text(
                  '${_t.version} ${item.currentVersion} · '
                  '${item.consentCurrent ? _t.upToDate : _t.needsAcceptance}',
                ),
                trailing: _busyPolicy == item.policy
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : item.consentCurrent
                        ? TextButton(
                            onPressed: () => _withdraw(item),
                            child: Text(_t.withdraw),
                          )
                        : FilledButton(
                            onPressed: () => _accept(item),
                            child: Text(_t.accept),
                          ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _historyTab(List<ConsentRecord>? history) {
    if (history == null) return const Center(child: CircularProgressIndicator());
    if (history.isEmpty) {
      return EmptyView(icon: Icons.history, title: _t.noConsents);
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: history.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, index) {
          final record = history[index];
          final withdrawn = record.withdrawnAt != null;
          return Card(
            child: ListTile(
              leading: Icon(
                withdrawn ? Icons.link_off : Icons.check_circle_outline,
                color: withdrawn
                    ? StarColors.textInverseMuted
                    : StarColors.success,
              ),
              title: Text(record.policyTitle),
              subtitle: Text([
                '${_t.version} ${record.version}',
                record.context,
                formatLegalDate(record.createdAt, widget.language),
                if (withdrawn)
                  '${_t.withdrawn} '
                      '${formatLegalDate(record.withdrawnAt, widget.language)}',
              ].join(' · ')),
            ),
          );
        },
      ),
    );
  }
}
