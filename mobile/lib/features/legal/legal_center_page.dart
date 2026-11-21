import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'consents_page.dart';
import 'legal_models.dart';
import 'legal_repository.dart';
import 'legal_strings.dart';
import 'policy_detail_page.dart';
import 'privacy_requests_page.dart';

/// Hub for policies, consents and privacy rights.
class LegalCenterPage extends StatefulWidget {
  const LegalCenterPage({super.key});

  @override
  State<LegalCenterPage> createState() => _LegalCenterPageState();
}

class _LegalCenterPageState extends State<LegalCenterPage> {
  late final LegalRepository _repository;
  String _language = 'en';
  bool _loading = true;
  Object? _error;
  List<PolicySummary> _policies = const [];
  List<ConsentStatusItem> _consents = const [];

  LegalStrings get _t => LegalStrings.forLanguage(_language);

  @override
  void initState() {
    super.initState();
    _repository = LegalRepository(context.read<AppSession>());
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final policies = await _repository.policies(_language);
      final consents = await _repository.consentStatus();
      if (!mounted) return;
      setState(() {
        _policies = policies;
        _consents = consents;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  void _setLanguage(String language) {
    if (language == _language) return;
    setState(() {
      _language = language;
      _policies = const [];
      _consents = const [];
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_t.title)),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Row(
              children: [
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'en', label: Text('EN')),
                    ButtonSegment(value: 'fr', label: Text('FR')),
                  ],
                  selected: {_language},
                  onSelectionChanged: (value) => _setLanguage(value.first),
                ),
                const Spacer(),
                IconButton(
                  tooltip: _t.retry,
                  onPressed: _loading ? null : _load,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
          ),
          Expanded(child: _body()),
        ],
      ),
    );
  }

  Widget _body() {
    if (_loading && _policies.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _policies.isEmpty) {
      final message = _error is ApiException
          ? (_error as ApiException).friendlyMessage
          : _t.loadFailed;
      return ErrorView(message: message, onRetry: _load);
    }
    final pending = _consents.where((item) => !item.consentCurrent).length;
    final grouped = <String, List<PolicySummary>>{};
    for (final policy in _policies) {
      grouped.putIfAbsent(policy.category, () => []).add(policy);
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Text(
            _t.subtitle,
            style: const TextStyle(color: StarColors.textInverseMuted),
          ),
          const SizedBox(height: 16),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.verified_user_outlined),
                  title: Text(_t.consents),
                  subtitle: Text(
                    pending == 0
                        ? _t.upToDate
                        : '$pending · ${_t.needsAcceptance}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => ConsentsPage(
                      repository: _repository,
                      language: _language,
                    ),
                  )),
                ),
                const Divider(height: 1),
                ListTile(
                  leading: const Icon(Icons.privacy_tip_outlined),
                  title: Text(_t.privacy),
                  subtitle: Text(_t.privacyIntro, maxLines: 2),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => PrivacyRequestsPage(
                      repository: _repository,
                      strings: _t,
                    ),
                  )),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          Text(_t.policies, style: Theme.of(context).textTheme.titleMedium),
          for (final entry in grouped.entries) ...[
            Padding(
              padding: const EdgeInsets.only(top: 14, bottom: 4),
              child: Text(
                categoryLabel(entry.key),
                style: const TextStyle(
                  color: StarColors.primary,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.3,
                ),
              ),
            ),
            Card(
              child: Column(
                children: [
                  for (var i = 0; i < entry.value.length; i++) ...[
                    if (i > 0) const Divider(height: 1),
                    _PolicyTile(
                      policy: entry.value[i],
                      language: _language,
                      strings: _t,
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => PolicyDetailPage(
                          repository: _repository,
                          slug: entry.value[i].slug,
                          language: _language,
                        ),
                      )),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _PolicyTile extends StatelessWidget {
  const _PolicyTile({
    required this.policy,
    required this.language,
    required this.strings,
    required this.onTap,
  });

  final PolicySummary policy;
  final String language;
  final LegalStrings strings;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    PublishedVersionBrief? current;
    for (final version in policy.publishedVersions) {
      if (version.language == language) {
        current = version;
        break;
      }
    }
    return ListTile(
      title: Text(policy.title),
      subtitle: Text(
        current == null
            ? '${policy.summary}\n${strings.notPublished}'
            : '${policy.summary}\n${strings.version} ${current.version} · '
                '${strings.effective} '
                '${formatLegalDate(current.effectiveDate, language)}',
        maxLines: 3,
        overflow: TextOverflow.ellipsis,
      ),
      isThreeLine: true,
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}
