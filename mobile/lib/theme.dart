import 'package:flutter/material.dart';

/// Design tokens mirroring DESIGN.md and web/src/styles/tokens.css.
/// Noir Teal / Liquid Glass: dark canvas, translucent glass cards with a rim,
/// teal #00adb5 as the single brand accent.
abstract final class StarColors {
  static const primary = Color(0xFF00adb5);
  static const primaryStrong = Color(0xFF222831);
  static const primarySoft = Color(0xFFb8eef0);

  static const canvas = Color(0xFF10161d);
  static const canvasDeep = Color(0xFF0b0f14);
  static const textInverse = Color(0xFFf2f6f7);
  static const textInverseMuted = Color(0xFFa9b4bd);

  static const glassTint = Color(0x8C222831); // rgba(34,40,49,.55)
  static const glassRim = Color(0x29F2F6F7); // rgba(242,246,247,.16)
  static const glassHighlight = Color(0x1AFFFFFF); // rgba(255,255,255,.10)
  static const navActiveBg = Color(0x2900adb5);

  static const success = Color(0xFF16a34a);
  static const warning = Color(0xFFd97706);
  static const danger = Color(0xFFdc2626);

  static const radiusSm = 4.0;
  static const radiusMd = 8.0;
  static const radiusLg = 12.0;
  static const radiusPill = 999.0;
}

extension StarStatusX on String {
  /// Human label and color for API lifecycle status values (logbook,
  /// assessments, placements, orders). Labels are plain-English mirrors of
  /// the API's status constants shown in the web app.
  (String, Color) get statusVisual {
    switch (this) {
      case 'draft':
        return ('Draft', StarColors.textInverseMuted);
      case 'submitted':
        return ('Submitted', StarColors.warning);
      case 'under_review':
        return ('Under review', StarColors.warning);
      case 'approved':
        return ('Approved', StarColors.success);
      case 'returned':
        return ('Returned', StarColors.danger);
      case 'needs_correction':
        return ('Needs correction', StarColors.danger);
      case 'rejected':
        return ('Rejected', StarColors.danger);
      case 'archived':
        return ('Archived', StarColors.textInverseMuted);
      case 'active':
        return ('Active', StarColors.success);
      case 'completed':
        return ('Completed', StarColors.textInverseMuted);
      case 'cancelled':
        return ('Cancelled', StarColors.danger);
      case 'pending_payment':
        return ('Pending payment', StarColors.warning);
      case 'paid':
        return ('Paid', StarColors.success);
      default:
        return (this, StarColors.textInverseMuted);
    }
  }
}

class StarGlass extends StatelessWidget {
  const StarGlass({super.key, required this.child, this.padding});
  final Widget child;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding ?? const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: StarColors.glassTint,
        borderRadius: BorderRadius.circular(StarColors.radiusLg),
        border: Border.all(color: StarColors.glassRim),
        boxShadow: const [
          BoxShadow(
            color: Color(0x66000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: child,
    );
  }
}

ThemeData buildStarTheme() {
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    fontFamily: 'AtkinsonHyperlegible',
    colorScheme: const ColorScheme.dark(
      primary: StarColors.primary,
      primaryContainer: StarColors.primaryStrong,
      secondary: StarColors.primary,
      surface: StarColors.canvas,
      error: StarColors.danger,
    ),
    scaffoldBackgroundColor: StarColors.canvasDeep,
  );

  return base.copyWith(
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: StarColors.textInverse,
      elevation: 0,
      centerTitle: false,
    ),
    textTheme: base.textTheme.apply(
      displayColor: StarColors.textInverse,
      bodyColor: StarColors.textInverse,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFF171E26),
      hintStyle: const TextStyle(color: StarColors.textInverseMuted),
      labelStyle: const TextStyle(color: StarColors.textInverseMuted),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(StarColors.radiusMd),
        borderSide: const BorderSide(color: StarColors.glassRim),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(StarColors.radiusMd),
        borderSide: const BorderSide(color: StarColors.glassRim),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(StarColors.radiusMd),
        borderSide: const BorderSide(color: StarColors.primary, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(StarColors.radiusMd),
        borderSide: const BorderSide(color: StarColors.danger),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: StarColors.primary,
        foregroundColor: StarColors.canvasDeep,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(StarColors.radiusPill),
        ),
        textStyle: const TextStyle(fontWeight: FontWeight.bold),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: StarColors.textInverse,
        side: const BorderSide(color: StarColors.glassRim),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(StarColors.radiusPill),
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: StarColors.primary),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: StarColors.canvas,
      indicatorColor: StarColors.navActiveBg,
      iconTheme: WidgetStateProperty.resolveWith((states) => IconThemeData(
              color: states.contains(WidgetState.selected)
                  ? StarColors.primary
                  : StarColors.textInverseMuted)),
      labelTextStyle: WidgetStateProperty.resolveWith((states) => TextStyle(
              color: states.contains(WidgetState.selected)
                  ? StarColors.primary
                  : StarColors.textInverseMuted,
              fontSize: 12,
              fontWeight: states.contains(WidgetState.selected)
                  ? FontWeight.bold
                  : FontWeight.w400)),
    ),
    cardTheme: CardThemeData(
      color: StarColors.glassTint,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(StarColors.radiusLg),
        side: const BorderSide(color: StarColors.glassRim),
      ),
      elevation: 0,
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: StarColors.primaryStrong,
      contentTextStyle: const TextStyle(color: StarColors.textInverse),
      behavior: SnackBarBehavior.floating,
    ),
    dividerTheme: const DividerThemeData(color: StarColors.glassRim),
  );
}
