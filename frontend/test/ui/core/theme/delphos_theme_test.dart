// Tests for the theme's tooltip look: a white card with a hairline, a 6 px
// radius, ink 12/500 text and the float shadow.
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_radius.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_shadows.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_theme.dart';
import 'package:delphos_frontend/ui/core/theme/type_scale.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('the tooltip theme matches the preview', () {
    final theme = buildDelphosTheme().tooltipTheme;
    final decoration = theme.decoration! as BoxDecoration;
    expect(decoration.color, DelphosColors.surface);
    expect(decoration.border, Border.all(color: DelphosColors.rule));
    expect(
      decoration.borderRadius,
      BorderRadius.circular(DelphosRadius.tooltip),
    );
    expect(decoration.boxShadow, DelphosShadows.float);
    expect(theme.textStyle!.fontSize, TypeScale.secondary);
    expect(theme.textStyle!.fontWeight, FontWeight.w500);
    expect(theme.textStyle!.color, DelphosColors.ink);
  });
}
