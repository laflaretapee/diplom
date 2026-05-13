import { theme } from 'antd';
import type { ThemeConfig } from 'antd';

export const lightTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    borderRadius: 6,
    colorPrimary: '#7C5815',
    colorInfo: '#7C5815',
    colorSuccess: '#389E0D',
    colorWarning: '#CA8A04',
    colorError: '#BA1A1A',
    colorLink: '#7C5815',
    colorBgBase: '#FCF9F8',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#F6F3F2',
    colorBorder: '#D3C4B3',
    colorText: '#1C1B1B',
    colorTextSecondary: '#4F4538',
    colorTextTertiary: '#817567',
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontFamilyCode: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace',
  },
  components: {
    Button: {
      defaultBg: '#FFFFFF',
      defaultBorderColor: '#E5E2E1',
      defaultColor: '#1C1B1B',
      primaryColor: '#694703',
      primaryShadow: '0 14px 30px rgba(232, 184, 109, 0.22)',
    },
    Input: {
      colorBgContainer: '#F6F3F2',
      colorBorder: '#E5E2E1',
      activeBorderColor: '#E8B86D',
      hoverBorderColor: '#EFBF73',
    },
    Layout: {
      bodyBg: '#FCF9F8',
      headerBg: '#FCF9F8',
      siderBg: '#FCF9F8',
      triggerBg: '#FCF9F8',
      triggerColor: '#1C1B1B',
    },
    Menu: {
      itemBg: '#FCF9F8',
      itemColor: '#4F4538',
      itemHoverBg: '#F6F3F2',
      itemHoverColor: '#7C5815',
      itemSelectedBg: '#FFDDAE',
      itemSelectedColor: '#604100',
    },
    Card: {
      colorBgContainer: '#FFFFFF',
      headerBg: '#FFFFFF',
      colorBorderSecondary: '#E5E2E1',
    },
    Select: {
      colorBgContainer: '#F6F3F2',
      colorBorder: '#E5E2E1',
      optionSelectedBg: '#FFDDAE',
      optionActiveBg: '#F6F3F2',
    },
    Table: {
      headerBg: '#F6F3F2',
      headerColor: '#4F4538',
      rowHoverBg: '#FCF9F8',
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
