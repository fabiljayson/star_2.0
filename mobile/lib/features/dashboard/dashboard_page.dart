import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/app_session.dart';
import '../../features/logbook/logbook_repository.dart';
import '../../theme.dart';
import '../../widgets/common.dart';

/// Post-sign-in home: payments-free summary + notifications preview.
class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardCounts {
  final Map<String, int> statusCounts;
  final int total;
  final int unreadNotifications;
  _DashboardCounts(this.statusCounts, this.total, this.unreadNotifications);
}

class _DashboardPageState extends State<DashboardPage> {
  late Future<_DashboardCounts> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  void _reload() => setState(() => _future = _load());

  Future<_DashboardCounts> _load() async {
    final session = context.read<AppSession>();
    final repo = LogbookRepository(session);
    final procedures = await repo.list(mineOnly: true, pageSize: 100);
    final counts = <String, int>{};
    for (final procedure in procedures) {
      counts[procedure.status] = (counts[procedure.status] ?? 0) + 1;
    }
    int unread = 0;
    try {
      final unreadData = session.api.getJson('notifications/unread-count/');
      final value = await unreadData;
      if (value case {'unread': final num n}) unread = n.toInt();
    } on ApiException {
      unread = -1;
    }
    return _DashboardCounts(counts, procedures.length, unread);
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<AppSession>();
    final user = session.user;
    return Scaffold(
      appBar: AppBar(title: const Text('STAR')),
      body: RefreshIndicator(
        onRefresh: () async => _reload(),
        child: FutureBuilder<_DashboardCounts>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return ListView(children: [
                const SizedBox(height: 80),
                ErrorView(
                  message: '${snapshot.error}',
                  onRetry: _reload,
                ),
              ]);
            }
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            final counts = snapshot.data!;
            final statuses = counts.statusCounts;
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              children: [
                StarGlass(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Welcome back,',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: StarColors.textInverseMuted,
                            ),
                      ),
                      Text(
                        user?.fullName.isEmpty == true ||
                                (user?.fullName ?? '').isEmpty
                            ? user?.email ?? ''
                            : user!.fullName,
                        style: Theme.of(context)
                            .textTheme
                            .headlineSmall
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        children: [
                          for (final role in user?.roleNames ?? const [])
                            StatusBadge(status: role),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'My surgical records',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                counts.total == 0
                    ? const EmptyView(
                        icon: Icons.description_outlined,
                        title: 'No records yet',
                        subtitle: 'Create one from the Logbook tab.',
                      )
                    : GridView.count(
                        crossAxisCount: 2,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        mainAxisSpacing: 12,
                        crossAxisSpacing: 12,
                        childAspectRatio: 1.9,
                        children: [
                          for (final entry in statuses.entries)
                            StarGlass(
                              padding: const EdgeInsets.all(12),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '${entry.value}',
                                    style: Theme.of(context)
                                        .textTheme
                                        .headlineMedium
                                        ?.copyWith(fontWeight: FontWeight.bold),
                                  ),
                                  const SizedBox(height: 4),
                                  StatusBadge(status: entry.key),
                                ],
                              ),
                            ),
                        ],
                      ),
                const SizedBox(height: 16),
                ListTile(
                  leading: const Icon(Icons.notifications_outlined),
                  title: const Text('Notifications'),
                  subtitle: Text(
                    counts.unreadNotifications >= 0
                        ? '${counts.unreadNotifications} unread'
                        : 'Unread count unavailable',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(StarColors.radiusLg),
                    side: const BorderSide(color: StarColors.glassRim),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
