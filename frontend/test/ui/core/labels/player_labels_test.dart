// Tests for the Spanish labels of positions, feet, leagues, valuation
// statuses and archetypes (DESIGN.md §3, the design preview's label maps).
import 'package:delphos_frontend/domain/models/valuation_status.dart';
import 'package:delphos_frontend/ui/core/labels/archetypes.dart';
import 'package:delphos_frontend/ui/core/labels/feet.dart';
import 'package:delphos_frontend/ui/core/labels/leagues.dart';
import 'package:delphos_frontend/ui/core/labels/positions.dart';
import 'package:delphos_frontend/ui/core/labels/valuation_labels.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('positions', () {
    test('map the three broad lines', () {
      expect(positionLabel('Attack'), 'Ataque');
      expect(positionLabel('Midfield'), 'Mediocampo');
      expect(positionLabel('Defender'), 'Defensa');
    });

    test('map all twelve sub-positions in sentence case', () {
      const expected = {
        'Centre-Forward': 'Delantero centro',
        'Right Winger': 'Extremo derecho',
        'Left Winger': 'Extremo izquierdo',
        'Second Striker': 'Segundo delantero',
        'Attacking Midfield': 'Mediapunta',
        'Central Midfield': 'Mediocentro',
        'Defensive Midfield': 'Pivote defensivo',
        'Right Midfield': 'Interior derecho',
        'Left Midfield': 'Interior izquierdo',
        'Centre-Back': 'Defensa central',
        'Right-Back': 'Lateral derecho',
        'Left-Back': 'Lateral izquierdo',
      };
      expected.forEach((key, label) => expect(subPositionLabel(key), label));
    });

    test('resolve the role from the sub-position, then the position', () {
      expect(
        roleLabel(position: 'Attack', subPosition: 'Right Winger'),
        'Extremo derecho',
      );
      expect(roleLabel(position: 'Attack', subPosition: 'Goalie'), 'Ataque');
      expect(roleLabel(position: 'Attack'), 'Ataque');
    });

    test('return null for an unknown key instead of the raw English', () {
      expect(positionLabel('Goalkeeper'), isNull);
      expect(subPositionLabel(null), isNull);
      expect(roleLabel(position: 'Goalkeeper'), isNull);
    });
  });

  group('feet', () {
    test('map right, left and both', () {
      expect(footLabel('right'), 'Diestro');
      expect(footLabel('left'), 'Zurdo');
      expect(footLabel('both'), 'Ambidiestro');
      expect(footLabel(null), isNull);
    });
  });

  group('leagues', () {
    test('map the fourteen league ids', () {
      const expected = {
        'GB1': 'Premier League',
        'ES1': 'LaLiga',
        'L1': 'Bundesliga',
        'IT1': 'Serie A',
        'FR1': 'Ligue 1',
        'PO1': 'Primeira Liga',
        'NL1': 'Eredivisie',
        'TR1': 'Süper Lig',
        'BE1': 'Pro League',
        'DK1': 'Superliga',
        'SC1': 'Premiership',
        'GR1': 'Super League',
        'UKR1': 'Premier Liga',
        'RU1': 'Premier Liga',
      };
      expected.forEach((id, label) => expect(leagueLabel(id), label));
    });

    test('return null for an unknown id, never the raw code', () {
      expect(leagueLabel('XX9'), isNull);
    });
  });

  group('valuation statuses', () {
    test('use the three approved verdicts', () {
      expect(
        valuationStatusLabel(ValuationStatus.undervalued),
        'Infravalorado',
      );
      expect(valuationStatusLabel(ValuationStatus.fair), 'En precio');
      expect(valuationStatusLabel(ValuationStatus.overvalued), 'Sobrevalorado');
    });

    test('parse from the API values only', () {
      expect(ValuationStatus.fromApi('fair'), ValuationStatus.fair);
      expect(ValuationStatus.fromApi('Fair'), isNull);
      expect(ValuationStatus.fromApi(null), isNull);
    });
  });

  group('archetypes', () {
    test('match the clustering stage names in delphos_domain', () {
      expect(archetypeShortName(0), 'Creador Ofensivo');
      expect(archetypeShortName(1), 'Box-to-Box');
      expect(archetypeShortName(2), 'Ancla Defensiva');
      expect(archetypeLongName(0), 'Creadores Ofensivos y Finalizadores');
      expect(archetypeLongName(1), 'Todocampistas Box-to-Box y Carrileros');
      expect(
        archetypeLongName(2),
        'Anclas Defensivas y Especialistas de Contención',
      );
    });

    test('return null for an unknown cluster', () {
      expect(archetypeShortName(7), isNull);
      expect(archetypeLongName(null), isNull);
    });
  });
}
