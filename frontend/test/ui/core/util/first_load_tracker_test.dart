// Tests for the first-load tracker: a view is claimed once, each view alone.
import 'package:delphos_frontend/ui/core/util/first_load_tracker.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('claims a view the first time only', () {
    final tracker = FirstLoadTracker();
    expect(tracker.claim('explorer'), isTrue);
    expect(tracker.claim('explorer'), isFalse);
    expect(tracker.claim('archetypes'), isTrue);
  });
}
