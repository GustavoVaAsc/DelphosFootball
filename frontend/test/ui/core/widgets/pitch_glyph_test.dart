// Tests for the mini pitch's zone placement: flanks for wingers and
// full-backs, the middle for centre players, the halfway line otherwise.
import 'package:delphos_frontend/ui/core/widgets/pitch_glyph.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('attackers sit in the attacking third, on their flank', () {
    final left = PitchGlyph.zoneFor('Attack', 'Left Winger');
    final right = PitchGlyph.zoneFor('Attack', 'Right Winger');
    final centre = PitchGlyph.zoneFor('Attack', 'Centre-Forward');
    expect(left.left, greaterThan(18));
    expect(left.center.dy, lessThan(12));
    expect(right.center.dy, greaterThan(12));
    expect(centre.center.dy, 12);
  });

  test('defenders sit in their own third and midfielders on halfway', () {
    expect(PitchGlyph.zoneFor('Defender', 'Centre-Back').right, lessThan(18));
    expect(
      PitchGlyph.zoneFor('Defender', 'Right-Back').center.dy,
      greaterThan(12),
    );
    final midfield = PitchGlyph.zoneFor('Midfield', 'Central Midfield');
    expect(midfield.left, lessThan(18));
    expect(midfield.right, greaterThan(18));
  });
}
