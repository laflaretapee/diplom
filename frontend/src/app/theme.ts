import { theme } from 'antd';
import type { ThemeConfig } from 'antd';

export const lightTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    borderRadius: 10,
    colorPrimary: '#C8832D',
    colorInfo: '#C8832D',
    colorSuccess: '#389E0D',
    colorWarning: '#D46B08',
    colorError: '#CF1322',
    colorLink: '#C8832D',
    colorBgBase: '#FDFAF7',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#F5F0EB',
    colorBorder: '#DED8D0',
    colorText: '#1A1714',
    colorTextSecondary: '#6B5F52',
    colorTextTertiary: '#9B8F80',
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontFamilyCode: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace',
  },
  components: {
    Button: {
      defaultBg: '#FFFFFF',
      defaultBorderColor: '#DED8D0',
      defaultColor: '#1A1714',
      primaryShadow: '0 14px 30px rgba(200, 131, 45, 0.20)',
    },
    Input: {
      colorBgContainer: '#FFFFFF',
      colorBorder: '#DED8D0',
      activeBorderColor: '#C8832D',
      hoverBorderColor: '#E8A050',
    },
    Layout: {
      bodyBg: '#F5F0EB',
      headerBg: '#FDFAF7',
      siderBg: '#FDFAF7',
      triggerBg: '#FDFAF7',
      triggerColor: '#1A1714',
    },
    Card: {
      colorBgContainer: '#FFFFFF',
      headerBg: '#FFFFFF',
      colorBorderSecondary: '#DED8D0',
    },
    Select: {
      colorBgContainer: '#FFFFFF',
      colorBorder: '#DED8D0',
      optionSelectedBg: '#FDF3E3',
      optionActiveBg: '#F5F0EB',
    },
    Table: {
      headerBg: '#F5F0EB',
      headerColor: '#6B5F52',
      rowHoverBg: '#FAF6F1',
    },
  },
};

export const appTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    borderRadius: 10,
    colorPrimary: '#E8B86D',
    colorInfo: '#E8B86D',
    colorSuccess: '#7CCFA2',
    colorWarning: '#E8B86D',
    colorError: '#FF9B97',
    colorLink: '#FFD598',
    colorBgBase: '#0E0E0E',
    colorBgContainer: '#201F1F',
    colorBgElevated: '#2A2A2A',
    colorBorder: '#4F4538',
    colorText: '#E5E2E1',
    colorTextSecondary: '#D3C4B3',
    colorTextTertiary: '#9B8F7F',
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontFamilyCode: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace',
  },
  components: {
    Button: {
      defaultBg: '#2A2A2A',
      defaultBorderColor: '#4F4538',
      defaultColor: '#E5E2E1',
      primaryShadow: '0 14px 30px rgba(232, 184, 109, 0.20)',
    },
    Input: {
      colorBgContainer: '#2A2A2A',
      colorBorder: '#4F4538',
      activeBorderColor: '#E8B86D',
      hoverBorderColor: '#FFD598',
    },
    Layout: {
      bodyBg: '#131313',
      headerBg: '#0E0E0E',
      siderBg: '#0E0E0E',
      triggerBg: '#0E0E0E',
      triggerColor: '#E5E2E1',
    },
    Menu: {
      darkItemBg: '#0E0E0E',
      darkSubMenuItemBg: '#0E0E0E',
      darkItemColor: 'rgba(229, 226, 225, 0.72)',
      darkItemHoverBg: '#201F1F',
      darkItemSelectedBg: '#2A2A2A',
      darkItemSelectedColor: '#FFD598',
    },
    Card: {
      colorBgContainer: '#201F1F',
      headerBg: '#201F1F',
      colorBorderSecondary: '#4F4538',
    },
    Select: {
      colorBgContainer: '#2A2A2A',
      colorBorder: '#4F4538',
      optionSelectedBg: '#2A2418',
      optionActiveBg: '#2A2A2A',
    },
    Table: {
      headerBg: '#2A2A2A',
      headerColor: '#D3C4B3',
      rowHoverBg: '#2A2A2A',
    },
  },
};
