// Widget test for FlagImage: a mapped country shows its bundled flag with a
// Spanish label; a country without a correct flag shows nothing.
import 'package:delphos_frontend/ui/core/widgets/flag_image.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  testWidgets('renders for a mapped country and not otherwise', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Row(
          children: [
            FlagImage(country: 'France'),
            FlagImage(country: 'Chinese Taipei'),
            FlagImage(country: 'Atlantis'),
            FlagImage(country: null),
          ],
        ),
      ),
    );
    expect(find.byType(Image), findsOneWidget);
    expect(find.bySemanticsLabel('Bandera de Francia'), findsOneWidget);
  });
}
