// Hover in widget tests. Flutter reports hover only in the "traditional"
// highlight mode, which a desktop browser is in and the test's default
// platform is not, so a test that hovers sets the mode first and puts it back.
import 'package:flutter/gestures.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

/// A mouse pointer for [tester], with hover enabled until the test ends.
Future<TestGesture> startHover(WidgetTester tester) async {
  FocusManager.instance.highlightStrategy =
      FocusHighlightStrategy.alwaysTraditional;
  addTearDown(
    () => FocusManager.instance.highlightStrategy =
        FocusHighlightStrategy.automatic,
  );
  final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
  await mouse.addPointer(location: Offset.zero);
  addTearDown(mouse.removePointer);
  return mouse;
}
