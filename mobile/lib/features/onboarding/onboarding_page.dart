import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/app_session.dart';
import '../../theme.dart';

/// First-launch tour: three slides, then straight to sign in.
class OnboardingPage extends StatefulWidget {
  const OnboardingPage({super.key});

  @override
  State<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends State<OnboardingPage> {
  final _pageController = PageController();
  int _index = 0;

  static const _slides = <_Slide>[
    _Slide(
      icon: Icons.description_outlined,
      title: 'Your surgical logbook',
      body: 'Record procedures, attach evidence and dictation, then submit '
          'them to your supervisor — from the operating room or the ward.',
    ),
    _Slide(
      icon: Icons.school_outlined,
      title: 'Training that tracks you',
      body: 'Competencies, assessments and examiner reviews stay attached to '
          'your placements, with clear progress on every requirement.',
    ),
    _Slide(
      icon: Icons.health_and_safety_outlined,
      title: 'Clinical data stays yours',
      body: 'Patient references are coded (never full names), attachments '
          'are private and every access is audited.',
    ),
  ];

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  Future<void> _finish() async {
    await context.read<AppSession>().completeOnboarding();
  }

  void _next() {
    if (_index >= _slides.length - 1) {
      _finish();
    } else {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 280),
        curve: Curves.easeOutCubic,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isLast = _index >= _slides.length - 1;
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(onPressed: _finish, child: const Text('Skip')),
              ),
              Expanded(
                child: PageView.builder(
                  controller: _pageController,
                  itemCount: _slides.length,
                  onPageChanged: (index) => setState(() => _index = index),
                  itemBuilder: (context, position) {
                    final slide = _slides[position];
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 16),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            decoration: const BoxDecoration(
                              shape: BoxShape.circle,
                              color: StarColors.glassTint,
                              border: Border.fromBorderSide(
                                BorderSide(color: StarColors.glassRim),
                              ),
                            ),
                            padding: const EdgeInsets.all(28),
                            child: Icon(slide.icon,
                                size: 48, color: StarColors.primary),
                          ),
                          const SizedBox(height: 28),
                          Text(
                            slide.title,
                            textAlign: TextAlign.center,
                            style: theme.textTheme.headlineSmall
                                ?.copyWith(fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 10),
                          Text(
                            slide.body,
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: StarColors.textInverseMuted,
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (var dot = 0; dot < _slides.length; dot++)
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      height: 8,
                      width: dot == _index ? 24 : 8,
                      decoration: BoxDecoration(
                        color: dot == _index
                            ? StarColors.primary
                            : StarColors.textInverseMuted.withValues(alpha: 0.4),
                        borderRadius:
                            BorderRadius.circular(StarColors.radiusPill),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  if (!isLast)
                    TextButton(
                      onPressed: _finish,
                      child: const Text('Go to sign in'),
                    ),
                  const Spacer(),
                  FilledButton.icon(
                    onPressed: _next,
                    icon: Icon(isLast
                        ? Icons.login
                        : Icons.arrow_forward_outlined),
                    label: Text(isLast ? 'Sign in' : 'Next'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Slide {
  const _Slide({required this.icon, required this.title, required this.body});
  final IconData icon;
  final String title;
  final String body;
}
