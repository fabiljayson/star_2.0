import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/app_session.dart';
import 'features/auth/login_page.dart';
import 'features/auth/mfa_page.dart';
import 'features/dashboard/dashboard_page.dart';
import 'features/logbook/logbook_list_page.dart';
import 'theme.dart';

/// Signed-in home with bottom navigation.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _tab,
        children: const [DashboardPage(), LogbookListPage()],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.description_outlined),
            selectedIcon: Icon(Icons.description),
            label: 'Logbook',
          ),
        ],
        onDestinationSelected: (index) => setState(() => _tab = index),
      ),
    );
  }
}

/// Root router driven by the session phase.
class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<AppSession>();
    return switch (session.phase) {
      AuthPhase.restoring => const BootScreen(),
      AuthPhase.requiresMfa => const MfaPage(),
      AuthPhase.signedOut => const LoginPage(),
      AuthPhase.signedIn => const HomeShell(),
    };
  }
}

class BootScreen extends StatelessWidget {
  const BootScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: StarColors.canvasDeep,
      body: const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: StarColors.primary),
            SizedBox(height: 16),
            Text('STAR', style: TextStyle(letterSpacing: 4, fontSize: 18)),
          ],
        ),
      ),
    );
  }
}
