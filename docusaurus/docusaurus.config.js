// Docusaurus-config voor de homelab-kennisbank.
// Gepubliceerd via Cloudflare Pages op https://homelab.westerweel.work.
// SCRUB-POLICY: nooit Tailscale 100.x-IP's, tokens, secrets of keys in de docs.
//   RFC1918-LAN (192.168.178.x) is toegestaan.

// @ts-check
const { themes } = require('prism-react-renderer');

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Homelab',
  tagline: 'Wat, hoe en waarom — Proxmox-cluster + HA-Kubernetes',
  favicon: 'img/favicon.ico',

  url: 'https://homelab.westerweel.work',
  baseUrl: '/',

  organizationName: 'MWest2020',
  projectName: 'homelab',

  onBrokenLinks: 'warn',

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'nl',
    locales: ['nl'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          routeBasePath: '/', // docs = site-root, geen aparte landingspagina nodig
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: 'https://github.com/MWest2020/homelab/tree/main/docusaurus/',
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'homelab',
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'docs',
            position: 'left',
            label: 'Docs',
          },
          {
            href: 'https://westerweel.work',
            label: 'westerweel.work',
            position: 'right',
          },
          {
            href: 'https://github.com/MWest2020/homelab',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'light',
        links: [],
        copyright:
          'Mark Westerweel — Platform & DevOps · <a href="https://westerweel.work">westerweel.work</a>',
      },
      prism: {
        theme: themes.github,
        darkTheme: themes.dracula,
      },
    }),
};

module.exports = config;
