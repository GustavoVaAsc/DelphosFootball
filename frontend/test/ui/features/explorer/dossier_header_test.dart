// Tests for the dossier header: the portrait beside the name, a one-line
// identity (flag, country, crest and club, league logo and league) and the
// Edad | Altura | Pie | Posición row. At the real 440 px panel the identity
// line never wraps and cuts only the club; a missing logo takes no space; a
// player with no season row takes the age from the birth date and has no
// league; no logos sit under the portrait; "Activo élite" is never shown.
import 'package:delphos_frontend/domain/models/player_profile.dart';
import 'package:delphos_frontend/domain/models/season_stats.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_colors.dart';
import 'package:delphos_frontend/ui/core/theme/delphos_text.dart';
import 'package:delphos_frontend/ui/core/widgets/player_avatar.dart';
import 'package:delphos_frontend/ui/core/widgets/remote_logo.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_definition_row.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_header.dart';
import 'package:delphos_frontend/ui/features/explorer/views/dossier_identity_line.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

const crestUrl = 'https://tmssl.akamaized.net/images/wappen/head/418.png';

SeasonStats season({String league = 'ES1'}) => SeasonStats(
  season: 2025,
  asOfDate: DateTime(2026, 5, 27),
  leagueId: league,
  minutes: 2400,
  apps: 30,
  starts: 28,
  goals: 5,
  assists: 1,
  yellowCards: 3,
  redCards: 0,
  starterRatio: 0.9,
  winRate: 0.5,
  cleanSheetRate: 0.3,
  goalsConcededPerMatch: 1.25,
  age: 25.4,
);

PlayerProfile profile({
  SeasonStats? season,
  String country = 'Brazil',
  String club = 'Real Madrid',
  String? clubLogoUrl,
}) => PlayerProfile(
  id: 1,
  name: 'Vinicius Junior',
  lastName: 'Junior',
  dateOfBirth: DateTime(2000, 7, 12),
  position: 'Attack',
  subPosition: 'Left Winger',
  transfermarktUrl: 'https://example.test/1',
  country: country,
  foot: 'right',
  heightCm: 176,
  clubName: club,
  clubLogoUrl: clubLogoUrl,
  season: season,
);

/// The header's real width in the 440 px panel: 20 px padding each side.
const double panelHeaderWidth = 400;

/// Pumps the header. With [settle] false it stops at the first frame, while
/// the (test-only, never answering) logo requests are still loading.
Future<void> pumpHeader(
  WidgetTester tester,
  PlayerProfile player, {
  double width = panelHeaderWidth,
  DateTime? dataDate,
  bool settle = true,
}) async {
  await loadArchivo();
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Align(
          alignment: Alignment.topLeft,
          child: SizedBox(
            width: width,
            child: DossierHeader(profile: player, dataDate: dataDate),
          ),
        ),
      ),
    ),
  );
  if (settle) await tester.pumpAndSettle();
}

/// A definition item's text ("Edad 25"), which is one rich text.
Finder item(String plain) => find.byWidgetPredicate(
  (widget) => widget is Text && widget.textSpan?.toPlainText() == plain,
);

Finder get logos => find.byType(RemoteLogo);

/// The width [text] takes in [style] where it is shown: the style is merged
/// with the inherited default (Material's text style adds a letter spacing
/// of 0,25 px), exactly as the `Text` widget does.
double textWidth(WidgetTester tester, String text, TextStyle style) {
  final inherited = DefaultTextStyle.of(tester.element(find.text(text))).style;
  return (TextPainter(
    text: TextSpan(text: text, style: inherited.merge(style)),
    textDirection: TextDirection.ltr,
  )..layout()).width;
}

void main() {
  testWidgets(
    'the lines read name, identity, definition row beside the portrait',
    (tester) async {
      await pumpHeader(tester, profile(season: season()));
      final avatar = tester.getRect(find.byType(PlayerAvatar));
      final name = tester.getRect(find.text('Vinicius Junior'));
      final identity = tester.getRect(find.byType(DossierIdentityLine));
      final definition = tester.getRect(find.byType(DossierDefinitionRow));
      expect(name.left, greaterThanOrEqualTo(avatar.right));
      expect(name.bottom, lessThanOrEqualTo(identity.top));
      expect(identity.bottom, lessThanOrEqualTo(definition.top));

      expect(item('Edad 25'), findsOneWidget);
      expect(item('Altura 1,76 m'), findsOneWidget);
      expect(item('Pie Diestro'), findsOneWidget);
      expect(item('Posición Extremo izquierdo'), findsOneWidget);
      expect(find.text('Activo élite'), findsNothing);
    },
  );

  testWidgets(
    'the logos are inline before their names, none under the portrait',
    (tester) async {
      await pumpHeader(
        tester,
        profile(season: season(), clubLogoUrl: crestUrl),
        settle: false,
      );
      // Only the identity line has logos: none under the portrait.
      expect(logos, findsNWidgets(2));
      expect(
        find.descendant(of: find.byType(DossierIdentityLine), matching: logos),
        findsNWidgets(2),
      );

      // While loading each logo reserves its 28 px height and no width, at the
      // start of its item: before the club name, and before the league name.
      final crest = tester.getRect(logos.first);
      final leagueLogo = tester.getRect(logos.last);
      final country = tester.getRect(find.text('Brasil'));
      final club = tester.getRect(find.text('Real Madrid'));
      final league = tester.getRect(find.text('LaLiga'));
      expect(crest.height, 28);
      expect(leagueLogo.height, 28);
      expect(crest.left, greaterThan(country.right));
      expect(crest.right, lessThanOrEqualTo(club.left));
      expect(leagueLogo.left, greaterThan(club.right));
      expect(leagueLogo.right, lessThanOrEqualTo(league.left));

      final avatar = tester.getRect(find.byType(PlayerAvatar));
      final identity = tester.getRect(find.byType(DossierIdentityLine));
      expect(identity.left, greaterThanOrEqualTo(avatar.right));
      await tester.pumpAndSettle();
    },
  );

  testWidgets(
    'at the 440 px panel the identity is one line, only the club cut',
    (tester) async {
      const club = 'Wolverhampton Wanderers';
      final semantics = tester.ensureSemantics();
      final player = profile(
        season: season(league: 'GB1'),
        country: 'United States',
        club: club,
        clubLogoUrl: crestUrl,
      );
      // Logos loading (28 px high), then failed (gone): one line either way.
      await pumpHeader(tester, player, settle: false);
      final line = tester.getRect(find.byType(DossierIdentityLine));
      expect(line.height, lessThanOrEqualTo(28.01), reason: 'one line');
      await tester.pumpAndSettle();
      expect(
        tester.getRect(find.byType(DossierIdentityLine)).height,
        lessThan(22),
        reason: 'one line',
      );
      expect(
        tester.getRect(find.byType(DossierIdentityLine)).right,
        lessThanOrEqualTo(panelHeaderWidth),
      );

      final plain = DelphosText.ui(color: DelphosColors.ink2);
      final bold = DelphosText.ui(
        color: DelphosColors.ink,
        weight: FontWeight.w600,
      );
      for (final text in ['Estados Unidos', 'Premier League']) {
        final box = tester.getRect(find.text(text));
        expect(box.height, lessThan(22), reason: '$text on one line');
        expect(
          box.width,
          closeTo(textWidth(tester, text, plain), 0.5),
          reason: text,
        );
      }
      final clubBox = tester.getRect(find.text(club));
      expect(
        clubBox.width,
        lessThan(textWidth(tester, club, bold)),
        reason: 'cut',
      );
      expect(
        tester.widget<Text>(find.text(club)).overflow,
        TextOverflow.ellipsis,
      );

      // The full name stays available to a screen reader.
      expect(
        find.bySemanticsLabel(RegExp('Wolverhampton Wanderers')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull, reason: 'no overflow');
      semantics.dispose();
    },
  );

  // Names that fit are never cut: España, FC Barcelona and LaLiga, and a
  // mid-length case, with logos loading (28 px reserved) and after they fail.
  final fitting = {
    'España · FC Barcelona · LaLiga': ('Spain', 'FC Barcelona', 'ES1'),
    'Países Bajos · Ajax · Eredivisie': ('Netherlands', 'Ajax', 'NL1'),
  };
  fitting.forEach((name, data) {
    final (country, club, league) = data;
    testWidgets('$name is shown in full', (tester) async {
      final player = profile(
        season: season(league: league),
        country: country,
        club: club,
        clubLogoUrl: crestUrl,
      );
      final plain = DelphosText.ui(color: DelphosColors.ink2);
      final bold = DelphosText.ui(
        color: DelphosColors.ink,
        weight: FontWeight.w600,
      );
      final parts = name.split(' · ');
      for (final settle in [false, true]) {
        await pumpHeader(tester, player, settle: settle);
        for (var i = 0; i < 3; i++) {
          final text = parts[i];
          final render = tester.renderObject<RenderParagraph>(find.text(text));
          expect(render.didExceedMaxLines, isFalse, reason: '$text $settle');
          expect(
            tester.getRect(find.text(text)).width,
            closeTo(textWidth(tester, text, i == 1 ? bold : plain), 0.5),
            reason: '$text $settle',
          );
        }
        expect(tester.takeException(), isNull);
      }
    });
  });

  testWidgets('a very long country is cut too, the league never is', (
    tester,
  ) async {
    const country = 'República Democrática del Congo';
    await pumpHeader(
      tester,
      profile(
        season: season(league: 'GB1'),
        country: 'DR Congo',
        club: 'Arsenal',
        clubLogoUrl: crestUrl,
      ),
      settle: false,
    );
    expect(tester.takeException(), isNull, reason: 'no overflow');
    final line = tester.getRect(find.byType(DossierIdentityLine));
    expect(line.height, lessThanOrEqualTo(28.01), reason: 'one line');

    final plain = DelphosText.ui(color: DelphosColors.ink2);
    final league = tester.getRect(find.text('Premier League'));
    expect(
      league.width,
      closeTo(textWidth(tester, 'Premier League', plain), 0.5),
    );
    expect(league.right, lessThanOrEqualTo(panelHeaderWidth));
    expect(tester.getRect(logos.last).right, lessThanOrEqualTo(league.left));
    final header = tester.getRect(find.byType(DossierHeader));
    expect(league.right, lessThanOrEqualTo(header.right));

    final countryBox = tester.getRect(find.text(country));
    expect(countryBox.width, lessThan(textWidth(tester, country, plain)));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('a missing or failed logo takes no space', (tester) async {
    // No crest URL (the league URL is built, but test images never load).
    await pumpHeader(tester, profile(season: season()));
    for (final element in logos.evaluate()) {
      expect(
        tester.getSize(find.byWidget(element.widget)),
        Size.zero,
        reason: 'a logo that is missing or failed leaves nothing',
      );
    }
    // With nothing before it, the club text starts right after its dot.
    final dots = find.descendant(
      of: find.byType(DossierIdentityLine),
      matching: find.text('·'),
    );
    final firstDot = tester.getRect(dots.first);
    final club = tester.getRect(find.text('Real Madrid'));
    expect(club.left - firstDot.right, closeTo(6, 0.5));
  });

  testWidgets('without a season row: age from the birth date, no league', (
    tester,
  ) async {
    await pumpHeader(
      tester,
      profile(clubLogoUrl: crestUrl),
      dataDate: DateTime(2026, 6, 5),
      settle: false,
    );
    expect(item('Edad 25'), findsOneWidget);
    expect(find.text('LaLiga'), findsNothing);
    expect(find.text('Real Madrid'), findsOneWidget);
    expect(find.text('Brasil'), findsOneWidget);
    // Only the crest: the league item and its separator are omitted.
    expect(logos, findsOneWidget);
    expect(
      find.descendant(
        of: find.byType(DossierIdentityLine),
        matching: find.text('·'),
      ),
      findsOneWidget,
    );
    await tester.pumpAndSettle();
  });

  testWidgets('the definition row wraps only between items', (tester) async {
    await pumpHeader(tester, profile(season: season()), width: 280);
    final labels = [
      'Edad 25',
      'Altura 1,76 m',
      'Pie Diestro',
      'Posición Extremo izquierdo',
    ];
    final rects = [for (final l in labels) tester.getRect(item(l))];
    expect(
      {for (final r in rects) r.top.roundToDouble()}.length,
      greaterThan(1),
    );
    for (final r in rects) {
      expect(r.height, lessThan(22), reason: 'an item wrapped inside');
    }
    expect(tester.takeException(), isNull);
  });
}
