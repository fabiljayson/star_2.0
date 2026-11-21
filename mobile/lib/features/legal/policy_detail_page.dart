import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'legal_models.dart';
import 'legal_repository.dart';
import 'legal_strings.dart';
import 'policy_history_page.dart';

/// Full text of one policy version, with in-page navigation and acceptance.
class PolicyDetailPage extends StatefulWidget {
  const PolicyDetailPage({
    super.key,
    required this.repository,
    required this.slug,
    required this.language,
  });

  final LegalRepository repository;
  final String slug;
  final String language;

  @override
  State<PolicyDetailPage> createState() => _PolicyDetailPageState();
}

class _PolicyDetailPageState extends State<PolicyDetailPage> {
  PolicyDetail? _detail;
  bool _loading = true;
  bool _stale = false;
  bool _accepting = false;
  bool _accepted = false;
  Object? _error;
  final Map<String, GlobalKey> _sectionKeys = {};

  LegalStrings get _t => LegalStrings.forLanguage(widget.language);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final detail = await widget.repository.policy(widget.slug, widget.language);
      if (!mounted) return;
      setState(() {
        _detail = detail;
        _stale = false;
        _loading = false;
        _sectionKeys
          ..clear()
          ..addEntries(sectionsOf(detail.body)
              .map((section) => MapEntry(section.id, GlobalKey())));
        _stale = false;
      });
    } catch (error) {
      if (!mounted) return;
      final cached = widget.repository.cachedPolicy(widget.slug, widget.language);
      setState(() {
        _loading = false;
        _error = cached == null ? error : null;
        _detail = cached;
        _stale = cached != null;
      });
    }
  }

  Future<void> _accept(PolicyDetail detail) async {
    setState(() => _accepting = true);
    try {
      await widget.repository.accept(
        policySlug: detail.slug,
        version: detail.version,
        language: detail.language,
      );
      if (!mounted) return;
      setState(() => _accepted = true);
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(content: Text(_t.accepted)));
    } catch (error) {
      if (mounted) showError(context, error);
    } finally {
      if (mounted) setState(() => _accepting = false);
    }
  }

  void _jumpTo(String id) {
    final context = _sectionKeys[id]?.currentContext;
    if (context == null) return;
    Scrollable.ensureVisible(
      context,
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      alignment: 0.05,
    );
  }

  @override
  Widget build(BuildContext context) {
    final detail = _detail;
    return Scaffold(
      appBar: AppBar(
        title: Text(detail?.title.isNotEmpty == true ? detail!.title : _t.title),
        actions: [
          IconButton(
            tooltip: _t.history,
            icon: const Icon(Icons.history),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => PolicyHistoryPage(
                repository: widget.repository,
                slug: widget.slug,
                language: widget.language,
              ),
            )),
          ),
        ],
      ),
      body: _body(detail),
      bottomNavigationBar: detail == null || detail.status != 'published'
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: FilledButton(
                  onPressed: _accepted || _accepting ? null : () => _accept(detail),
                  child: _accepting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(_accepted ? _t.accepted : _t.accept),
                ),
              ),
            ),
    );
  }

  Widget _body(PolicyDetail? detail) {
    if (_loading && detail == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (detail == null) {
      final message =
          _error is ApiException ? (_error as ApiException).friendlyMessage : _t.loadFailed;
      return ErrorView(message: message, onRetry: _load);
    }
    final sections = sectionsOf(detail.body);
    final meta = [
      '${_t.version} ${detail.version}',
      if (detail.effectiveDate != null)
        '${_t.effective} ${formatLegalDate(detail.effectiveDate, widget.language)}',
    ].join(' · ');

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          if (_stale)
            _Notice(
              icon: Icons.cloud_off_outlined,
              color: StarColors.warning,
              text: _t.staleNotice,
            ),
          if (detail.status != 'published')
            _Notice(
              icon: Icons.edit_note,
              color: StarColors.warning,
              text: _t.draftNotice,
            ),
          Text(detail.title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 6),
          Text(
            '$meta · ${detail.language.toUpperCase()}',
            style: const TextStyle(color: StarColors.textInverseMuted),
          ),
          if (sections.isNotEmpty) ...[
            const SizedBox(height: 12),
            SizedBox(
              height: 36,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: sections.length,
                separatorBuilder: (_, _) => const SizedBox(width: 8),
                itemBuilder: (context, index) {
                  final section = sections[index];
                  return ActionChip(
                    label: Text(section.heading),
                    onPressed: () => _jumpTo(section.id),
                  );
                },
              ),
            ),
          ],
          const SizedBox(height: 12),
          for (final section in sections) ...[
            Padding(
              key: _sectionKeys[section.id],
              padding: const EdgeInsets.only(top: 12, bottom: 6),
              child: Text(
                section.heading,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            _RichText(section.body),
          ],
          if (sections.isEmpty) _RichText(detail.body),
        ],
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.color, required this.text});

  final IconData icon;
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(StarColors.radiusMd),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: TextStyle(color: color))),
        ],
      ),
    );
  }
}

/// Minimal Markdown renderer for policy text: paragraphs, bullets, bold.
/// The backend stores plain Markdown headings (`##`) plus simple emphasis.
class _RichText extends StatelessWidget {
  const _RichText(this.source);

  final String source;

  @override
  Widget build(BuildContext context) {
    final blocks = <Widget>[];
    final paragraph = <String>[];

    void flushParagraph() {
      if (paragraph.isEmpty) return;
      blocks.add(Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text.rich(_span(paragraph.join(' '))),
      ));
      paragraph.clear();
    }

    for (final raw in source.split('\n')) {
      final line = raw.trimRight();
      if (line.trim().isEmpty) {
        flushParagraph();
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        flushParagraph();
        blocks.add(Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('•  '),
              Expanded(child: Text.rich(_span(line.substring(2)))),
            ],
          ),
        ));
      } else {
        paragraph.add(line.trim());
      }
    }
    flushParagraph();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: blocks);
  }

  static TextSpan _span(String text) {
    final spans = <TextSpan>[];
    final pattern = RegExp(r'\*\*(.+?)\*\*');
    var index = 0;
    for (final match in pattern.allMatches(text)) {
      if (match.start > index) {
        spans.add(TextSpan(text: text.substring(index, match.start)));
      }
      spans.add(TextSpan(
        text: match.group(1),
        style: const TextStyle(fontWeight: FontWeight.w600),
      ));
      index = match.end;
    }
    if (index < text.length) spans.add(TextSpan(text: text.substring(index)));
    return TextSpan(children: spans);
  }
}
