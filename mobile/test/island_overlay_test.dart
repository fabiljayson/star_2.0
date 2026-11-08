import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:star_mobile/features/notifications/dynamic_island.dart';

void main() {
  testWidgets('IslandOverlay builds without Directionality error', (
    WidgetTester tester,
  ) async {
    // Build a MaterialApp that provides the necessary inherited widgets,
    // including Directionality.
    await tester.pumpWidget(
      MaterialApp(
        home: IslandOverlay(
          controller: IslandController(),
          child: SizedBox.shrink(),
        ),
      ),
    );

    // If we reach this point without throwing, the test passes.
    expect(tester.widget<IslandOverlay>(find.byType(IslandOverlay)), isNotNull);
  });
}
