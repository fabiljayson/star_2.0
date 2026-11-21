import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/app_session.dart';
import 'features/auth/login_page.dart';
import 'features/auth/mfa_page.dart';
import 'features/dashboard/dashboard_page.dart';
import 'features/legal/legal_center_page.dart';
import 'features/legal/terms_update_banner.dart';
import 'features/logbook/logbook_list_page.dart';
import 'features/marketplace/orders_page.dart';
import 'features/notifications/notifications_page.dart';
import 'features/onboarding/onboarding_page.dart';
import 'theme.dart';

const _buyerRoles = {'buyer', 'platform_admin', 'supplier'};

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
    final session = context.watch<AppSession>();
    final user = session.user;
    final hasOrdersAccess = user != null &&
        (user.isPlatformAdmin ||
            user.roleNames.any((role) => _buyerRoles.contains(role)));
    final pages = <Widget>[
      const DashboardPage(),
      const LogbookListPage(),
      if (hasOrdersAccess) const OrdersPage(),
      const NotificationsPage(),
      const LegalCenterPage(),
    ];
    final destinations = <Widget>[
      const NavigationDestination(
        icon: Icon(Icons.dashboard_outlined),
        selectedIcon: Icon(Icons.dashboard),
        label: 'Home',
      ),
      const NavigationDestination(
        icon: Icon(Icons.description_outlined),
        selectedIcon: Icon(Icons.description),
        label: 'Logbook',
      ),
      if (hasOrdersAccess)
        const NavigationDestination(
          icon: Icon(Icons.receipt_long_outlined),
          selectedIcon: Icon(Icons.receipt_long),
          label: 'Orders',
        ),
      const NavigationDestination(
        icon: Icon(Icons.notifications_outlined),
        selectedIcon: Icon(Icons.notifications),
        label: 'Alerts',
      ),
      const NavigationDestination(
        icon: Icon(Icons.policy_outlined),
        selectedIcon: Icon(Icons.policy),
        label: 'Legal',
      ),
    ];
    final tab = _tab.clamp(0, pages.length - 1);
    return Scaffold(
      body: Column(
        children: [
          const TermsUpdateBanner(),
          Expanded(child: IndexedStack(index: tab, children: pages)),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        destinations: [for (final dest in destinations) dest],
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
      AuthPhase.signedOut => const FirstRunGate(),
      AuthPhase.signedIn => const HomeShell(),
    };
  }
}

/// Almost-instant gate: first launch shows the tour, then the login form.
class FirstRunGate extends StatelessWidget {
  const FirstRunGate({super.key});

  @override
  Widget build(BuildContext context) {
    final seenOnboarding = context.watch<AppSession>().onboardingDone;
    if (!seenOnboarding) return const OnboardingPage();
    return const LoginPage();
  }
}

/// Branded loading screen shown while the session is restored.
class BootScreen extends StatelessWidget {
  const BootScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: StarColors.canvasDeep,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                color: StarColors.glassTint,
                border: Border.fromBorderSide(
                  BorderSide(color: StarColors.glassRim, width: 1.2),
                ),
              ),
              child: const Icon(Icons.medical_services_outlined,
                  size: 44, color: StarColors.primary),
            ),
            const SizedBox(height: 20),
            const Text(
              'STAR',
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.bold,
                letterSpacing: 8,
                color: StarColors.textInverse,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Surgical tracking & assessment',
              style: TextStyle(
                fontSize: 12,
                color: StarColors.textInverseMuted,
              ),
            ),
            const SizedBox(height: 28),
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(
                strokeWidth: 2.4,
                color: StarColors.primary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
