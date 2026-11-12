/// The app's paths and their page titles (ADR-024).
library;

/// Route paths. `/` redirects to [explorer]; there is no chat route yet.
abstract final class Routes {
  static const String root = '/';
  static const String explorer = '/explorador';
  static const String comparator = '/comparador';
  static const String archetypes = '/arquetipos';

  /// The browser tab title of the app itself, and of a page outside the
  /// three modules.
  static const String appTitle = 'DelphosFootball · Dirección Deportiva';

  /// The comparator with [playerId] as the reference player.
  static String comparatorFor(int playerId) => '$comparator/$playerId';

  /// The page title of a path, or `null` outside the three modules.
  static String? titleFor(String path) =>
      switch (Uri.parse(path).pathSegments) {
        ['explorador'] => 'Explorador de Mercado',
        ['comparador', ...] => 'Comparador Moneyball',
        ['arquetipos'] => 'Arquetipos Tácticos',
        _ => null,
      };

  /// The browser tab title of a path: "Explorador de Mercado ·
  /// DelphosFootball" for a module, [appTitle] otherwise.
  static String documentTitleFor(String path) => switch (titleFor(path)) {
    final title? => '$title · DelphosFootball',
    null => appTitle,
  };
}
