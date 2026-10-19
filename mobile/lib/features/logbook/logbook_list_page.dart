import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_session.dart';
import '../../theme.dart';
import '../../widgets/common.dart';
import 'procedure.dart';
import 'procedure_create_page.dart';
import 'procedure_detail_page.dart';

/// List of surgical records with status filter.
class LogbookListPage extends StatefulWidget {
  const LogbookListPage({super.key});

  @override
  State<LogbookListPage> createState() => _LogbookListPageState();
}

class _LogbookListPageState extends State<LogbookListPage> {
  String? _statusFilter;
  late Future<List<Procedure>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  void _reload() => setState(() => _future = _load());

  Future<List<Procedure>> _load() => context
      .read<AppSession>()
      .api
      .getJson(
        'procedures/',
        query: {
          'page_size': '25',
          if (_statusFilter?.isNotEmpty == true) 'status': _statusFilter!,
        },
      )
      .then((data) {
        if (data case {'results': final List results}) {
          return results
              .whereType<Map<String, dynamic>>()
              .map(Procedure.fromJson)
              .toList();
        }
        return const <Procedure>[];
      });

  @override
  Widget build(BuildContext context) {
    const statuses = ['', 'draft', 'submitted', 'approved', 'returned', 'archived'];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Logbook'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'New record',
            onPressed: () async {
              await Navigator.of(context).push<Procedure>(
                MaterialPageRoute(builder: (_) => const ProcedureCreatePage()),
              );
              _reload();
            },
          ),
        ],
      ),
      body: Column(
        children: [
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                for (final status in statuses)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      selected: _statusFilter == status,
                      label: Text(
                        status.isEmpty ? 'All' : status.statusVisual.$1,
                      ),
                      selectedColor: StarColors.primary.withValues(alpha: 0.25),
                      labelStyle: TextStyle(
                        color: _statusFilter == status
                            ? StarColors.primary
                            : StarColors.textInverseMuted,
                        fontWeight: FontWeight.bold,
                      ),
                      side: BorderSide(
                        color: _statusFilter == status
                            ? StarColors.primary
                            : StarColors.glassRim,
                      ),
                      onSelected: (_) {
                        setState(
                          () => _statusFilter = status.isEmpty ? null : status,
                        );
                        _reload();
                      },
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: FutureBuilder<List<Procedure>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return ErrorView(message: '${snapshot.error}', onRetry: _reload);
                }
                if (!snapshot.hasData) {
                  return const Center(child: CircularProgressIndicator());
                }
                final items = snapshot.data!;
                if (items.isEmpty) {
                  return const EmptyView(
                    icon: Icons.description_outlined,
                    title: 'No records',
                    subtitle: 'Tap + to add your first surgical record.',
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async => _reload(),
                  child: ListView.separated(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    itemCount: items.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final procedure = items[index];
                      return ProcedureTile(procedure: procedure);
                    },
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class ProcedureTile extends StatelessWidget {
  const ProcedureTile({super.key, required this.procedure});

  final Procedure procedure;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(StarColors.radiusLg),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ProcedureDetailPage(procedureId: procedure.id),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      procedure.procedureName,
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontWeight: FontWeight.bold),
                    ),
                  ),
                  StatusBadge(status: procedure.status),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                '${procedure.reference} · ${_dateLabel(procedure.procedureDate)}',
                style: const TextStyle(color: StarColors.textInverseMuted),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

String _dateLabel(String isoDate) {
  final parts = isoDate.split('-');
  if (parts.length != 3) return isoDate;
  return '${parts[2]}/${parts[1]}/${parts[0]}';
}
