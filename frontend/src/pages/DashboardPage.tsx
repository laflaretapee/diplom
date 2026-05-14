import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  BarChartOutlined,
  CalendarOutlined,
  FireOutlined,
  ReloadOutlined,
  ShopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Col, Row, Select, Space, Tag, Typography } from 'antd';

import { apiClient } from '../api/client';
import { roleMeta } from '../auth/roleMeta';
import { useAuthStore } from '../auth/store';
import type { Role } from '../auth/types';
import { useIsMobileLayout } from '../hooks/useIsMobileLayout';

type Period = 'day' | 'week' | 'month';

interface PointRead {
  id: string;
  name: string;
  address?: string;
  is_active?: boolean;
  franchisee_id?: string | null;
}

interface RevenuePointItem {
  point_id: string;
  point_name: string;
  total_revenue: string | number;
  order_count: number;
}

interface DishAnalyticsItem {
  dish_name: string;
  total_quantity: string | number;
  total_revenue: string | number;
}

interface DishesAnalyticsResponse {
  top: DishAnalyticsItem[];
  bottom: DishAnalyticsItem[];
}

interface ChannelAnalyticsItem {
  source_channel: string;
  order_count: number;
  total_revenue: string | number;
}

interface AnalyticsSummaryResponse {
  total_orders_today: number;
  total_revenue_today: string | number;
  pending_orders: number;
  top_dish_today: string | null;
}

const ALL_POINTS = '__all__';
const PERIOD_OPTIONS: { value: Period; label: string }[] = [
  { value: 'day', label: 'Сегодня' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
];
const PERIOD_LABELS: Record<Period, string> = {
  day: 'Сегодня',
  week: 'Неделя',
  month: 'Месяц',
};

const CHANNEL_LABELS: Record<string, string> = {
  website: 'Сайт',
  mobile_app: 'Приложение',
  telegram: 'Телеграм',
  vk: 'ВКонтакте',
  pos: 'Касса',
};

const DASHBOARD_SHELL_STYLE = {
  background: 'var(--j-surface-strong)',
  border: '1px solid var(--j-surface-high)',
  boxShadow: '0 18px 48px var(--j-shadow)',
};

const PANEL_STYLE = {
  background: 'var(--j-surface-panel)',
  border: '1px solid var(--j-surface-high)',
  boxShadow: 'none',
};

function authHeader(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function isPointCentric(role: Role): boolean {
  return role === 'point_manager' || role === 'staff';
}

function asNumber(value: string | number | null | undefined): number {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function formatMoney(value: string | number | null | undefined): string {
  return `${asNumber(value).toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ₽`;
}

function formatMonoNumber(value: string | number | null | undefined): string {
  return asNumber(value).toLocaleString('ru-RU');
}

function formatId(value: string): string {
  return value.slice(0, 8).toUpperCase();
}

function channelLabel(channel: string): string {
  return CHANNEL_LABELS[channel] ?? channel.replace(/_/g, ' ');
}

function periodLabel(period: Period): string {
  return PERIOD_LABELS[period];
}

function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const maybeError = error as { response?: { data?: { message?: unknown } }; message?: unknown };
    const message = maybeError.response?.data?.message ?? maybeError.message;
    if (typeof message === 'string' && message.trim()) {
      return message;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return 'Не удалось загрузить данные.';
}

function SectionStateBlock({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  const isMobile = useIsMobileLayout();

  return (
    <div
      style={{
        minHeight: isMobile ? 132 : 150,
        borderRadius: 14,
        border: '1px dashed var(--j-border-strong)',
        background: 'var(--j-surface-muted)',
        padding: isMobile ? 16 : 20,
        display: 'grid',
        placeItems: 'center',
        textAlign: 'center',
      }}
    >
      <Space direction="vertical" size={12} style={{ width: '100%', maxWidth: 440 }}>
        <Typography.Text style={{ color: 'var(--j-text)', fontSize: isMobile ? 13 : 14, fontWeight: 600 }}>
          {title}
        </Typography.Text>
        <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 12, lineHeight: 1.6 }}>
          {description}
        </Typography.Text>
        {action}
      </Space>
    </div>
  );
}

async function fetchPoints(token: string | null): Promise<PointRead[]> {
  const { data } = await apiClient.get<PointRead[]>('/v1/points', {
    headers: authHeader(token),
  });
  return data;
}

async function fetchRevenue(
  token: string | null,
  period: Period,
  pointId?: string,
): Promise<RevenuePointItem[]> {
  const { data } = await apiClient.get<RevenuePointItem[]>('/v1/analytics/revenue', {
    headers: authHeader(token),
    params: { period, ...(pointId ? { point_id: pointId } : {}) },
  });
  return data;
}

async function fetchChannels(
  token: string | null,
  period: Period,
  pointId?: string,
): Promise<ChannelAnalyticsItem[]> {
  const { data } = await apiClient.get<ChannelAnalyticsItem[]>('/v1/analytics/channels', {
    headers: authHeader(token),
    params: { period, ...(pointId ? { point_id: pointId } : {}) },
  });
  return data;
}

async function fetchDishes(
  token: string | null,
  period: Period,
  pointId?: string,
): Promise<DishesAnalyticsResponse> {
  const { data } = await apiClient.get<DishesAnalyticsResponse>('/v1/analytics/dishes', {
    headers: authHeader(token),
    params: { period, limit: 5, ...(pointId ? { point_id: pointId } : {}) },
  });
  return data;
}

async function fetchSummary(
  token: string | null,
  pointId: string,
): Promise<AnalyticsSummaryResponse> {
  const { data } = await apiClient.get<AnalyticsSummaryResponse>('/v1/analytics/summary', {
    headers: authHeader(token),
    params: { point_id: pointId },
  });
  return data;
}

function usePointOrdersWS(
  pointId: string | null,
  token: string | null,
  enabled: boolean,
  onEvent: () => void,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!enabled || !pointId || !token) {
      return undefined;
    }

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = import.meta.env.VITE_WS_HOST ?? 'localhost:18000';
      const url = `${protocol}://${host}/api/v1/ws/orders/${pointId}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data as string) as { type?: string };
          if (msg.type === 'order_created' || msg.type === 'order_status_changed') {
            onEventRef.current();
          }
        } catch {
          // Ignore malformed events and keep listening.
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (cancelled) return;
        reconnectTimerRef.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled, pointId, token]);
}

function MetricCard({
  title,
  value,
  icon,
  hint,
  tone = 'amber',
}: {
  title: string;
  value: string;
  icon: ReactNode;
  hint?: string;
  tone?: 'amber' | 'red' | 'default';
}) {
  const isMobile = useIsMobileLayout();
  const accent = tone === 'red' ? '#ff7d7d' : tone === 'amber' ? '#FFD598' : 'var(--j-text)';

  return (
    <Card
      bordered={false}
      style={{ ...PANEL_STYLE, height: '100%' }}
      styles={{ body: { padding: isMobile ? 14 : 20 } }}
    >
      <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }}>
        <div style={{ minWidth: 0 }}>
          <Typography.Text
            style={{
              display: 'block',
              color: 'var(--j-text-secondary)',
              fontSize: 11,
              letterSpacing: '0.16em',
              textTransform: 'uppercase',
            }}
          >
            {title}
          </Typography.Text>
          <Typography.Text
            style={{
              display: 'block',
              marginTop: 8,
              color: 'var(--j-text)',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: isMobile ? 22 : 30,
              fontWeight: 700,
              lineHeight: 1.1,
              whiteSpace: isMobile ? 'nowrap' : 'normal',
              overflow: isMobile ? 'hidden' : 'visible',
              textOverflow: isMobile ? 'ellipsis' : 'clip',
            }}
          >
            {value}
          </Typography.Text>
          {hint ? (
            <Typography.Text style={{ display: 'block', marginTop: 8, color: 'var(--j-text-tertiary)', fontSize: 12 }}>
              {hint}
            </Typography.Text>
          ) : null}
        </div>
        <div
          style={{
            flex: '0 0 auto',
            width: isMobile ? 36 : 42,
            height: isMobile ? 36 : 42,
            borderRadius: 10,
            border: '1px solid var(--j-border-strong)',
            background: 'linear-gradient(180deg, rgba(255, 213, 152, 0.14), rgba(255, 213, 152, 0.06))',
            color: accent,
            display: 'grid',
            placeItems: 'center',
          }}
        >
          {icon}
        </div>
      </Space>
    </Card>
  );
}

function SectionCard({
  title,
  subtitle,
  extra,
  children,
}: {
  title: string;
  subtitle?: string;
  extra?: ReactNode;
  children: ReactNode;
}) {
  const isMobile = useIsMobileLayout();

  return (
    <Card bordered={false} style={PANEL_STYLE} styles={{ body: { padding: isMobile ? 16 : 20 } }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Space
          direction={isMobile ? 'vertical' : 'horizontal'}
          style={{ width: '100%', justifyContent: 'space-between' }}
          align="start"
          size={isMobile ? 8 : 12}
        >
          <div>
            <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0, color: 'var(--j-text)' }}>
              {title}
            </Typography.Title>
            {subtitle ? <Typography.Text style={{ color: 'var(--j-text-tertiary)' }}>{subtitle}</Typography.Text> : null}
          </div>
          {extra}
        </Space>
        {children}
      </Space>
    </Card>
  );
}

function BarRow({
  label,
  value,
  detail,
  percent,
}: {
  label: string;
  value: string;
  detail?: string;
  percent: number;
}) {
  return (
    <Space direction="vertical" size={6} style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
        <Typography.Text style={{ color: 'var(--j-text)' }}>{label}</Typography.Text>
        <Typography.Text style={{ color: '#FFD598', fontFamily: '"JetBrains Mono", monospace' }}>
          {value}
        </Typography.Text>
      </Space>
      <div style={{ height: 8, borderRadius: 999, background: 'var(--j-surface-high)', overflow: 'hidden' }}>
        <div
          style={{
            width: `${Math.max(6, Math.min(100, percent))}%`,
            height: '100%',
            borderRadius: 999,
            background: 'linear-gradient(90deg, #E8B86D 0%, #FFD598 100%)',
          }}
        />
      </div>
      {detail ? <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 12 }}>{detail}</Typography.Text> : null}
    </Space>
  );
}

export function DashboardPage() {
  const isMobile = useIsMobileLayout();
  const token = useAuthStore((state) => state.token);
  const name = useAuthStore((state) => state.name);
  const role = useAuthStore((state) => state.role);
  const queryClient = useQueryClient();

  const [period, setPeriod] = useState<Period>('week');
  const [selectedPointId, setSelectedPointId] = useState<string | null>(role && isPointCentric(role) ? null : ALL_POINTS);
  const pointCentric = role ? isPointCentric(role) : false;

  const pointsQuery = useQuery({
    queryKey: ['dashboard-points', token],
    queryFn: () => fetchPoints(token),
    enabled: Boolean(token && role),
    retry: false,
  });

  const points = Array.isArray(pointsQuery.data) ? pointsQuery.data : [];

  useEffect(() => {
    if (points.length === 0) {
      setSelectedPointId(pointCentric ? null : ALL_POINTS);
      return;
    }

    if (pointCentric) {
      const exists = selectedPointId !== null && points.some((point) => point.id === selectedPointId);
      if (!exists) {
        setSelectedPointId(points[0].id);
      }
      return;
    }

    if (selectedPointId !== ALL_POINTS && !points.some((point) => point.id === selectedPointId)) {
      setSelectedPointId(ALL_POINTS);
    }
  }, [pointCentric, points, selectedPointId]);

  const selectedPoint =
    selectedPointId && selectedPointId !== ALL_POINTS
      ? points.find((point) => point.id === selectedPointId) ?? null
      : null;

  const accessiblePointId = pointCentric
    ? selectedPointId && selectedPointId !== ALL_POINTS
      ? selectedPointId
      : undefined
    : selectedPointId && selectedPointId !== ALL_POINTS
      ? selectedPointId
      : undefined;

  const revenueQuery = useQuery({
    queryKey: ['dashboard', 'network', 'revenue', period, accessiblePointId ?? 'all'],
    queryFn: () => fetchRevenue(token, period, accessiblePointId),
    enabled: Boolean(token && role && !pointCentric),
    retry: false,
    refetchInterval: 45_000,
  });

  const channelsQuery = useQuery({
    queryKey: ['dashboard', 'network', 'channels', period, accessiblePointId ?? 'all'],
    queryFn: () => fetchChannels(token, period, accessiblePointId),
    enabled: Boolean(token && role && !pointCentric),
    retry: false,
    refetchInterval: 45_000,
  });

  const dishesQuery = useQuery({
    queryKey: ['dashboard', 'network', 'dishes', period, accessiblePointId ?? 'all'],
    queryFn: () => fetchDishes(token, period, accessiblePointId),
    enabled: Boolean(token && role && !pointCentric),
    retry: false,
    refetchInterval: 45_000,
  });

  const summaryQuery = useQuery({
    queryKey: ['dashboard', 'point', 'summary', selectedPointId ?? 'none'],
    queryFn: () => fetchSummary(token, selectedPointId ?? ''),
    enabled: Boolean(token && role && pointCentric && selectedPointId && selectedPointId !== ALL_POINTS),
    retry: false,
    refetchInterval: 30_000,
  });

  const pointChannelsQuery = useQuery({
    queryKey: ['dashboard', 'point', 'channels', selectedPointId ?? 'none'],
    queryFn: () => fetchChannels(token, 'day', selectedPointId ?? ''),
    enabled: Boolean(token && role && pointCentric && selectedPointId && selectedPointId !== ALL_POINTS),
    retry: false,
    refetchInterval: 30_000,
  });

  usePointOrdersWS(
    pointCentric ? (selectedPointId && selectedPointId !== ALL_POINTS ? selectedPointId : null) : null,
    token,
    pointCentric && Boolean(selectedPointId) && selectedPointId !== ALL_POINTS,
    () => {
      void queryClient.invalidateQueries({ queryKey: ['dashboard', 'point'] });
    },
  );

  const handleRefresh = () => {
    if (pointCentric) {
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'point'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-points'] }),
      ]);
      return;
    }

    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'network'] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard-points'] }),
    ]);
  };

  const pointOptions = [
    ...(pointCentric ? [] : [{ value: ALL_POINTS, label: 'Все точки' }]),
    ...points.map((point) => ({
      value: point.id,
      label: point.name,
    })),
  ];

  const refreshing =
    pointsQuery.isFetching ||
    revenueQuery.isFetching ||
    channelsQuery.isFetching ||
    dishesQuery.isFetching ||
    summaryQuery.isFetching ||
    pointChannelsQuery.isFetching;

  const availablePointsCount = pointCentric ? points.length : points.length;

  if (!role) {
    return null;
  }

  const meta = roleMeta[role];

  return (
    <Space direction="vertical" size={isMobile ? 16 : 24} style={{ width: '100%', color: 'var(--j-text)' }}>
      <Card
        bordered={false}
        style={DASHBOARD_SHELL_STYLE}
        styles={{ body: { padding: isMobile ? 16 : 24 } }}
      >
        <Space direction="vertical" size={14} style={{ width: '100%' }}>
          <Space
            direction={isMobile ? 'vertical' : 'horizontal'}
            style={{ width: '100%', justifyContent: 'space-between' }}
            align="start"
            wrap={!isMobile}
            size={12}
          >
            <div>
              <Typography.Title level={isMobile ? 4 : 3} style={{ margin: 0, color: '#FFD598' }}>
                {pointCentric ? 'Дашборд точки' : 'Дашборд сети'}
              </Typography.Title>
              <Typography.Text style={{ color: 'var(--j-text-secondary)' }}>
                {meta.description}
                {name ? ` • ${name}` : ''}
              </Typography.Text>
            </div>
            <Space direction={isMobile ? 'vertical' : 'horizontal'} wrap={!isMobile} style={{ width: isMobile ? '100%' : undefined }}>
              <Tag
                color="default"
                style={{
                  marginInlineEnd: 0,
                  background: 'var(--j-surface-panel)',
                  borderColor: 'var(--j-border-strong)',
                  color: '#FFD598',
                  fontFamily: '"JetBrains Mono", monospace',
                }}
              >
                {meta.label}
              </Tag>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={refreshing}
                block={isMobile}
                style={{
                  background: 'var(--j-surface-high)',
                  color: 'var(--j-text)',
                  borderColor: 'var(--j-border-strong)',
                }}
              >
                Обновить
              </Button>
            </Space>
          </Space>

          <Row gutter={[12, 12]} align="bottom">
            {!pointCentric ? (
              <Col xs={24} md={8} xl={6}>
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 11, letterSpacing: '0.16em' }}>
                    Период
                  </Typography.Text>
                  <Select
                    value={period}
                    onChange={(value: Period) => setPeriod(value)}
                    options={PERIOD_OPTIONS}
                    style={{ width: '100%' }}
                    popupMatchSelectWidth
                    notFoundContent="Нет доступных периодов"
                  />
                </Space>
              </Col>
            ) : null}
            <Col xs={24} md={pointCentric ? 14 : 10} xl={pointCentric ? 10 : 8}>
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 11, letterSpacing: '0.16em' }}>
                  {pointCentric ? 'Точка' : 'Фильтр по точке'}
                </Typography.Text>
                  <Select
                    value={selectedPointId ?? undefined}
                    onChange={(value: string) => setSelectedPointId(value)}
                    options={pointOptions}
                    loading={pointsQuery.isLoading}
                    style={{ width: '100%' }}
                    notFoundContent={pointsQuery.isError ? 'Не удалось загрузить точки' : 'Нет доступных точек'}
                  />
                </Space>
              </Col>
            <Col xs={24} md={pointCentric ? 10 : 6} xl={pointCentric ? 8 : 6}>
              <Card
                bordered={false}
                style={{
                  ...PANEL_STYLE,
                  height: '100%',
                  background: 'var(--j-surface-muted)',
                }}
                styles={{ body: { padding: isMobile ? 12 : 14 } }}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 11, letterSpacing: '0.16em' }}>
                    Контур
                  </Typography.Text>
                  <Typography.Text
                    style={{
                      color: '#FFD598',
                      fontFamily: '"JetBrains Mono", monospace',
                      fontWeight: 600,
                      fontSize: 14,
                    }}
                  >
                    {pointCentric
                      ? selectedPoint?.name ?? (pointsQuery.isLoading ? 'Загрузка точек...' : 'Выберите точку')
                      : selectedPoint?.name ?? `Все точки (${availablePointsCount})`}
                  </Typography.Text>
                  <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 12 }}>
                    {pointCentric
                      ? 'Обновление идет через веб-сокет с резервным переподключением.'
                      : 'Автообновление выполняется каждые 45 секунд.'}
                  </Typography.Text>
                </Space>
              </Card>
            </Col>
          </Row>
        </Space>
      </Card>

      {pointCentric ? (
        <PointDashboardCard
          pointId={selectedPointId}
          pointName={selectedPoint?.name ?? null}
          summary={summaryQuery.data ?? null}
          summaryLoading={summaryQuery.isLoading}
          summaryError={summaryQuery.error}
          summaryFetching={summaryQuery.isFetching}
          channels={pointChannelsQuery.data ?? []}
          channelsLoading={pointChannelsQuery.isLoading}
          channelsError={pointChannelsQuery.error}
          channelsFetching={pointChannelsQuery.isFetching}
          pointsLoading={pointsQuery.isLoading}
          pointsError={pointsQuery.isError}
          onRetrySummary={() => void summaryQuery.refetch()}
          onRetryChannels={() => void pointChannelsQuery.refetch()}
        />
      ) : (
        <NetworkDashboardCard
          revenue={revenueQuery.data ?? []}
          revenueLoading={revenueQuery.isLoading}
          revenueError={revenueQuery.error}
          revenueFetching={revenueQuery.isFetching}
          channels={channelsQuery.data ?? []}
          channelsLoading={channelsQuery.isLoading}
          channelsError={channelsQuery.error}
          channelsFetching={channelsQuery.isFetching}
          dishes={dishesQuery.data?.top ?? []}
          dishesLoading={dishesQuery.isLoading}
          dishesError={dishesQuery.error}
          dishesFetching={dishesQuery.isFetching}
          period={period}
          selectedPointId={selectedPointId}
          selectedPointName={selectedPoint?.name ?? null}
          onRetryRevenue={() => void revenueQuery.refetch()}
          onRetryChannels={() => void channelsQuery.refetch()}
          onRetryDishes={() => void dishesQuery.refetch()}
        />
      )}
    </Space>
  );
}

function NetworkDashboardCard({
  revenue,
  revenueLoading,
  revenueError,
  revenueFetching,
  channels,
  channelsLoading,
  channelsError,
  channelsFetching,
  dishes,
  dishesLoading,
  dishesError,
  dishesFetching,
  period,
  selectedPointId,
  selectedPointName,
  onRetryRevenue,
  onRetryChannels,
  onRetryDishes,
}: {
  revenue: RevenuePointItem[];
  revenueLoading: boolean;
  revenueError: unknown;
  revenueFetching: boolean;
  channels: ChannelAnalyticsItem[];
  channelsLoading: boolean;
  channelsError: unknown;
  channelsFetching: boolean;
  dishes: DishAnalyticsItem[];
  dishesLoading: boolean;
  dishesError: unknown;
  dishesFetching: boolean;
  period: Period;
  selectedPointId: string | null;
  selectedPointName: string | null;
  onRetryRevenue: () => void;
  onRetryChannels: () => void;
  onRetryDishes: () => void;
}) {
  const isMobile = useIsMobileLayout();
  const safeRevenue = Array.isArray(revenue) ? revenue : [];
  const safeChannels = Array.isArray(channels) ? channels : [];
  const safeDishes = Array.isArray(dishes) ? dishes : [];

  const sortedRevenue = [...safeRevenue].sort((left, right) => asNumber(right.total_revenue) - asNumber(left.total_revenue));
  const totalRevenue = sortedRevenue.reduce((sum, item) => sum + asNumber(item.total_revenue), 0);
  const totalOrders = sortedRevenue.reduce((sum, item) => sum + (item.order_count ?? 0), 0);
  const scopePoints = selectedPointId && selectedPointId !== ALL_POINTS ? 1 : sortedRevenue.length;
  const topPoint = sortedRevenue[0] ?? null;
  const avgTicket = totalOrders > 0 ? totalRevenue / totalOrders : 0;
  const topDish = safeDishes[0] ?? null;
  const maxRevenue = Math.max(1, ...sortedRevenue.map((item) => asNumber(item.total_revenue)));
  const maxChannelOrders = Math.max(1, ...safeChannels.map((item) => item.order_count));
  const revenueHasData = safeRevenue.length > 0;
  const channelsHasData = safeChannels.length > 0;
  const dishesHasData = safeDishes.length > 0;
  const revenueInitialLoading = revenueLoading && !revenueHasData;
  const channelsInitialLoading = channelsLoading && !channelsHasData;
  const dishesInitialLoading = dishesLoading && !dishesHasData;
  const revenueDegraded = Boolean(revenueError) && revenueHasData;
  const channelsDegraded = Boolean(channelsError) && channelsHasData;
  const dishesDegraded = Boolean(dishesError) && dishesHasData;
  const networkDegraded = revenueDegraded || channelsDegraded || dishesDegraded;

  return (
    <Space direction="vertical" size={isMobile ? 16 : 24} style={{ width: '100%' }}>
      <Card
        bordered={false}
        style={PANEL_STYLE}
        styles={{ body: { padding: isMobile ? 14 : 16 } }}
      >
        <Space align="center" size={10} wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <div>
            <Typography.Text style={{ color: 'var(--j-text)', fontWeight: 600 }}>
              {networkDegraded ? 'Часть секций работает с ограничениями' : 'Все секции доступны'}
            </Typography.Text>
            <Typography.Text style={{ display: 'block', marginTop: 4, color: 'var(--j-text-tertiary)', fontSize: 12 }}>
              {networkDegraded
                ? 'Показываем последние доступные данные и отдельные статусы по каждой секции.'
                : 'Данные по выручке, каналам и блюдам обновляются независимо.'}
            </Typography.Text>
          </div>
          <Tag
            color="default"
            style={{
              marginInlineEnd: 0,
              background: networkDegraded ? 'var(--j-warning-bg)' : 'var(--j-surface-panel)',
              borderColor: networkDegraded ? 'var(--j-border)' : 'var(--j-border-strong)',
              color: networkDegraded ? '#E8B86D' : '#FFD598',
              fontFamily: '"JetBrains Mono", monospace',
            }}
          >
            {networkDegraded ? 'ЧАСТИЧНО' : 'ГОТОВО'}
          </Tag>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={12} sm={12} xl={6}>
          <MetricCard
            title="Выручка"
            value={revenueInitialLoading ? 'Загрузка...' : revenueError && !revenueHasData ? 'Недоступно' : formatMoney(totalRevenue)}
            icon={<BarChartOutlined />}
            hint={
              revenueInitialLoading
                ? 'Загружаем выручку по точкам...'
                : revenueError && !revenueHasData
                  ? getErrorMessage(revenueError)
                  : revenueError && revenueHasData
                    ? 'Показаны последние доступные данные по выручке.'
                    : topPoint
                      ? `Лучшая точка: ${topPoint.point_name}`
                      : `Период: ${periodLabel(period)}`
            }
            tone={revenueError && !revenueHasData ? 'red' : 'amber'}
          />
        </Col>
        <Col xs={12} sm={12} xl={6}>
          <MetricCard
            title="Заказы"
            value={revenueInitialLoading ? 'Загрузка...' : revenueError && !revenueHasData ? 'Недоступно' : formatMonoNumber(totalOrders)}
            icon={<CalendarOutlined />}
            hint={
              revenueInitialLoading
                ? 'Загружаем количество заказов...'
                : revenueError && !revenueHasData
                  ? 'Сводка заказов временно недоступна.'
                  : revenueError && revenueHasData
                    ? 'Показаны последние доступные данные по заказам.'
                    : 'Без отменённых заказов'
            }
            tone={revenueError && !revenueHasData ? 'red' : 'default'}
          />
        </Col>
        <Col xs={12} sm={12} xl={6}>
          <MetricCard
            title="Точек в контуре"
            value={revenueInitialLoading ? 'Загрузка...' : revenueError && !revenueHasData ? 'Недоступно' : formatMonoNumber(scopePoints)}
            icon={<ShopOutlined />}
            hint={
              revenueInitialLoading
                ? 'Определяем доступные точки...'
                : revenueError && !revenueHasData
                  ? 'Невозможно определить точки без данных.'
                  : revenueError && revenueHasData
                    ? 'Ограничение по секции выручки, доступ к точкам сохранён.'
                    : selectedPointName
                      ? selectedPointName
                      : 'Все доступные точки'
            }
            tone={revenueError && !revenueHasData ? 'red' : 'default'}
          />
        </Col>
        <Col xs={12} sm={12} xl={6}>
          <MetricCard
            title="Средний чек"
            value={revenueInitialLoading ? 'Загрузка...' : revenueError && !revenueHasData ? 'Недоступно' : formatMoney(avgTicket)}
            icon={<ThunderboltOutlined />}
            hint={
              revenueInitialLoading
                ? 'Считаем средний чек...'
                : revenueError && !revenueHasData
                  ? 'Средний чек недоступен без выручки.'
                  : revenueError && revenueHasData
                    ? 'Показаны последние доступные данные по среднему чеку.'
                    : topDish
                      ? `Лучшее блюдо: ${topDish.dish_name}`
                      : 'Нет данных по выручке'
            }
            tone={revenueError && !revenueHasData ? 'red' : 'amber'}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <SectionCard
            title="Выручка по точкам"
            subtitle="Ленты показывают вклад каждой точки внутри выбранного контура."
            extra={
              <Tag
                color="default"
                style={{
                  marginInlineEnd: 0,
                  background: revenueDegraded ? 'var(--j-warning-bg)' : 'var(--j-surface-panel)',
                  borderColor: revenueInitialLoading || revenueDegraded ? 'var(--j-border)' : 'var(--j-border-strong)',
                  color: revenueInitialLoading ? 'var(--j-text)' : revenueDegraded ? '#E8B86D' : '#FFD598',
                }}
              >
                {revenueInitialLoading
                  ? 'ЗАГРУЗКА'
                  : revenueDegraded
                    ? 'ЧАСТИЧНО'
                    : revenueError && !revenueHasData
                      ? 'ОШИБКА'
                      : 'ГОТОВО'}
              </Tag>
            }
          >
            {revenueInitialLoading ? (
              <SectionStateBlock
                title="Загружаем выручку"
                description="Запрашиваем данные по точкам. Секция появится сразу после первого успешного ответа."
              />
            ) : revenueError && !revenueHasData ? (
              <SectionStateBlock
                title="Выручка недоступна"
                description={getErrorMessage(revenueError)}
                action={
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={onRetryRevenue}
                    style={{
                      background: 'var(--j-surface-high)',
                      color: 'var(--j-text)',
                      borderColor: 'var(--j-border-strong)',
                    }}
                  >
                    Повторить
                  </Button>
                }
              />
            ) : sortedRevenue.length > 0 ? (
              <Space direction="vertical" size={14} style={{ width: '100%' }}>
                {revenueDegraded ? (
                  <Typography.Text style={{ color: '#E8B86D', fontSize: 12 }}>
                    Показаны последние доступные данные по выручке.
                  </Typography.Text>
                ) : null}
                {sortedRevenue.slice(0, 8).map((item) => (
                  <BarRow
                    key={item.point_id}
                    label={item.point_name}
                    value={formatMoney(item.total_revenue)}
                    detail={`${formatMonoNumber(item.order_count)} заказов`}
                    percent={(asNumber(item.total_revenue) / maxRevenue) * 100}
                  />
                ))}
              </Space>
            ) : (
              <SectionStateBlock
                title="Нет данных по выручке"
                description="За выбранный период и фильтр выручка не вернулась."
              />
            )}
          </SectionCard>
        </Col>

        <Col xs={24} xl={10}>
          <SectionCard
            title="Каналы"
            subtitle="Распределение трафика за тот же период."
            extra={
              <Tag
                color="default"
                style={{
                  marginInlineEnd: 0,
                  background: channelsDegraded ? 'var(--j-warning-bg)' : 'var(--j-surface-panel)',
                  borderColor: channelsInitialLoading || channelsDegraded ? 'var(--j-border)' : 'var(--j-border-strong)',
                  color: channelsInitialLoading ? 'var(--j-text)' : channelsDegraded ? '#E8B86D' : '#FFD598',
                }}
              >
                {channelsInitialLoading
                  ? 'ЗАГРУЗКА'
                  : channelsDegraded
                    ? 'ЧАСТИЧНО'
                    : channelsError && !channelsHasData
                      ? 'ОШИБКА'
                      : 'ГОТОВО'}
              </Tag>
            }
          >
            {channelsInitialLoading ? (
              <SectionStateBlock
                title="Загружаем каналы"
                description="Пока ожидаем ответ аналитики по каналам продаж."
              />
            ) : channelsError && !channelsHasData ? (
              <SectionStateBlock
                title="Каналы недоступны"
                description={getErrorMessage(channelsError)}
                action={
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={onRetryChannels}
                    style={{
                      background: 'var(--j-surface-high)',
                      color: 'var(--j-text)',
                      borderColor: 'var(--j-border-strong)',
                    }}
                  >
                    Повторить
                  </Button>
                }
              />
            ) : safeChannels.length > 0 ? (
              <Space direction="vertical" size={14} style={{ width: '100%' }}>
                {channelsDegraded ? (
                  <Typography.Text style={{ color: '#E8B86D', fontSize: 12 }}>
                    Показаны последние доступные данные по каналам.
                  </Typography.Text>
                ) : null}
                {safeChannels.map((channel) => (
                  <div
                    key={channel.source_channel}
                    style={{
                      padding: '12px 14px',
                      borderRadius: 10,
                      border: '1px solid var(--j-surface-high)',
                      background: 'var(--j-surface-muted)',
                    }}
                  >
                    <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
                      <div>
                        <Typography.Text style={{ color: 'var(--j-text)' }}>
                          {channelLabel(channel.source_channel)}
                        </Typography.Text>
                        <Typography.Text
                          style={{ display: 'block', marginTop: 4, color: 'var(--j-text-tertiary)', fontSize: 12 }}
                        >
                          {formatMonoNumber(channel.order_count)} заказов
                        </Typography.Text>
                      </div>
                      <Typography.Text style={{ color: '#FFD598', fontFamily: '"JetBrains Mono", monospace' }}>
                        {formatMoney(channel.total_revenue)}
                      </Typography.Text>
                    </Space>
                    <div style={{ height: 8, marginTop: 10, borderRadius: 999, background: 'var(--j-surface-high)' }}>
                      <div
                        style={{
                          width: `${Math.max(8, (channel.order_count / maxChannelOrders) * 100)}%`,
                          height: '100%',
                          borderRadius: 999,
                          background: 'linear-gradient(90deg, #FFD598 0%, #E8B86D 100%)',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </Space>
            ) : (
              <SectionStateBlock
                title="Нет данных по каналам"
                description="Для выбранного периода данные по каналам не вернулись."
              />
            )}
          </SectionCard>
        </Col>
      </Row>

      <SectionCard
        title="Топ блюд"
        subtitle="Топ-5 блюд для выбранного контура."
        extra={
          <Tag
            color="default"
            style={{
              marginInlineEnd: 0,
              background: dishesDegraded ? 'var(--j-warning-bg)' : 'var(--j-surface-panel)',
              borderColor: dishesInitialLoading || dishesDegraded ? 'var(--j-border)' : 'var(--j-border-strong)',
              color: dishesInitialLoading ? 'var(--j-text)' : dishesDegraded ? '#E8B86D' : '#FFD598',
            }}
          >
            {dishesInitialLoading
              ? 'ЗАГРУЗКА'
              : dishesDegraded
                ? 'ЧАСТИЧНО'
                : dishesError && !dishesHasData
                  ? 'ОШИБКА'
                  : 'ГОТОВО'}
          </Tag>
        }
      >
        {dishesInitialLoading ? (
          <SectionStateBlock
            title="Загружаем блюда"
            description="Собираем топ блюд по текущему периоду и фильтру."
          />
        ) : dishesError && !dishesHasData ? (
          <SectionStateBlock
            title="Блюда недоступны"
            description={getErrorMessage(dishesError)}
            action={
              <Button
                icon={<ReloadOutlined />}
                onClick={onRetryDishes}
                style={{
                  background: 'var(--j-surface-high)',
                  color: 'var(--j-text)',
                  borderColor: 'var(--j-border-strong)',
                }}
              >
                Повторить
              </Button>
            }
          />
        ) : safeDishes.length > 0 ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {dishesDegraded ? (
              <Typography.Text style={{ color: '#E8B86D', fontSize: 12 }}>
                Показаны последние доступные данные по блюдам.
              </Typography.Text>
            ) : null}
            {safeDishes.map((dish, index) => (
              <div
                key={dish.dish_name}
                style={{
                  padding: '12px 14px',
                  borderRadius: 10,
                  border: '1px solid var(--j-surface-high)',
                  background: 'var(--j-surface-muted)',
                }}
              >
                <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
                  <Space align="start" size={10}>
                    <Tag
                      color="default"
                      style={{
                        marginInlineEnd: 0,
                        background: 'var(--j-surface-high)',
                        borderColor: 'var(--j-border-strong)',
                        color: '#FFD598',
                        fontFamily: '"JetBrains Mono", monospace',
                      }}
                    >
                      #{index + 1}
                    </Tag>
                    <div>
                      <Typography.Text style={{ color: 'var(--j-text)' }}>{dish.dish_name}</Typography.Text>
                      <Typography.Text style={{ display: 'block', marginTop: 4, color: 'var(--j-text-tertiary)', fontSize: 12 }}>
                        {formatMonoNumber(dish.total_quantity)} шт.
                      </Typography.Text>
                    </div>
                  </Space>
                  <Typography.Text style={{ color: '#FFD598', fontFamily: '"JetBrains Mono", monospace' }}>
                    {formatMoney(dish.total_revenue)}
                  </Typography.Text>
                </Space>
              </div>
            ))}
          </Space>
        ) : (
          <SectionStateBlock
            title="Нет данных по блюдам"
            description="Для выбранного периода топ блюд не вернулся."
          />
        )}
      </SectionCard>
    </Space>
  );
}

function PointDashboardCard({
  pointId,
  pointName,
  summary,
  summaryLoading,
  summaryError,
  summaryFetching,
  channels,
  channelsLoading,
  channelsError,
  channelsFetching,
  pointsLoading,
  pointsError,
  onRetrySummary,
  onRetryChannels,
}: {
  pointId: string | null;
  pointName: string | null;
  summary: AnalyticsSummaryResponse | null;
  summaryLoading: boolean;
  summaryError: unknown;
  summaryFetching: boolean;
  channels: ChannelAnalyticsItem[];
  channelsLoading: boolean;
  channelsError: unknown;
  channelsFetching: boolean;
  pointsLoading: boolean;
  pointsError: boolean;
  onRetrySummary: () => void;
  onRetryChannels: () => void;
}) {
  const isMobile = useIsMobileLayout();
  const safeChannels = Array.isArray(channels) ? channels : [];
  const maxChannelOrders = Math.max(1, ...safeChannels.map((item) => item.order_count));
  const summaryHasData = Boolean(summary);
  const channelsHasData = safeChannels.length > 0;
  const summaryInitialLoading = summaryLoading && !summaryHasData;
  const channelsInitialLoading = channelsLoading && !channelsHasData;
  const summaryDegraded = Boolean(summaryError) && summaryHasData;
  const channelsDegraded = Boolean(channelsError) && channelsHasData;

  return (
    <Space direction="vertical" size={isMobile ? 16 : 24} style={{ width: '100%' }}>
      <Card
        bordered={false}
        style={PANEL_STYLE}
        styles={{ body: { padding: isMobile ? 14 : 16 } }}
      >
        <Space align="center" size={10} wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <div>
            <Typography.Text style={{ color: 'var(--j-text)', fontWeight: 600 }}>
              {summaryInitialLoading || channelsInitialLoading
                ? 'Загружаем данные точки'
                : summaryDegraded || channelsDegraded
                  ? 'Часть данных точки недоступна'
                  : pointsError
                    ? 'Список точек недоступен'
                    : 'Точка готова к показу'}
            </Typography.Text>
            <Typography.Text style={{ display: 'block', marginTop: 4, color: 'var(--j-text-tertiary)', fontSize: 12 }}>
              {summaryInitialLoading || channelsInitialLoading
                ? 'Секции загружаются независимо, чтобы не терять уже доступные данные.'
                : summaryDegraded || channelsDegraded
                  ? 'Показываем последнюю успешную сводку и отдельные статусы по секциям.'
                  : pointsLoading
                    ? 'Загружаем список точек для переключения.'
                    : 'Данные обновляются по веб-сокету и резервному опросу.'}
            </Typography.Text>
          </div>
          <Tag
            color="default"
            style={{
              marginInlineEnd: 0,
              background:
                summaryInitialLoading || channelsInitialLoading ? '#1F251D' : summaryDegraded || channelsDegraded ? 'var(--j-warning-bg)' : 'var(--j-surface-panel)',
              borderColor: 'var(--j-border-strong)',
              color: summaryInitialLoading || channelsInitialLoading ? '#B5E8C0' : summaryDegraded || channelsDegraded ? '#E8B86D' : '#FFD598',
              fontFamily: '"JetBrains Mono", monospace',
            }}
          >
            {summaryInitialLoading || channelsInitialLoading ? 'ЗАГРУЗКА' : summaryDegraded || channelsDegraded ? 'ЧАСТИЧНО' : 'ГОТОВО'}
          </Tag>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={12} sm={12} xl={6}>
          <MetricCard
            title="Заказы за сегодня"
            value={summaryInitialLoading ? 'Загрузка...' : summaryError && !summaryHasData ? 'Недоступно' : formatMonoNumber(summary?.total_orders_today ?? 0)}
            icon={<CalendarOutlined />}
            hint={
              summaryInitialLoading
                ? 'Загружаем сводку по точке...'
                : summaryError && !summaryHasData
                  ? getErrorMessage(summaryError)
                  : summaryDegraded
                    ? 'Показаны последние доступные данные по заказам.'
                    : pointName ?? 'Выбранная точка'
            }
            tone={summaryError && !summaryHasData ? 'red' : 'default'}
          />
        </Col>
        <Col xs={12} sm={12} xl={6}>
          <MetricCard
            title="Выручка за сегодня"
            value={summaryInitialLoading ? 'Загрузка...' : summaryError && !summaryHasData ? 'Недоступно' : formatMoney(summary?.total_revenue_today ?? 0)}
            icon={<BarChartOutlined />}
            hint={
              summaryInitialLoading
                ? 'Считаем дневную выручку...'
                : summaryError && !summaryHasData
                  ? 'Дневная выручка недоступна.'
                  : summaryDegraded
                    ? 'Показаны последние доступные данные по выручке.'
                    : 'Обновляется из сводного эндпоинта'
            }
            tone={summaryError && !summaryHasData ? 'red' : 'default'}
          />
        </Col>
        <Col xs={12} sm={12} xl={6}>
          <MetricCard
            title="Активные заказы"
            value={summaryInitialLoading ? 'Загрузка...' : summaryError && !summaryHasData ? 'Недоступно' : formatMonoNumber(summary?.pending_orders ?? 0)}
            icon={<ThunderboltOutlined />}
            hint={
              summaryInitialLoading
                ? 'Смотрим активные заказы...'
                : summaryError && !summaryHasData
                  ? 'Сводка активных заказов временно недоступна.'
                  : summaryDegraded
                    ? 'Показаны последние доступные данные по активным заказам.'
                    : 'Новые + в работе + готовые'
            }
            tone={summaryError && !summaryHasData ? 'red' : (summary?.pending_orders ?? 0) > 0 ? 'red' : 'default'}
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <MetricCard
            title="Топ-блюдо дня"
            value={summaryInitialLoading ? 'Загрузка...' : summaryError && !summaryHasData ? 'Недоступно' : summary?.top_dish_today ?? 'Нет данных'}
            icon={<FireOutlined />}
            hint={
              summaryInitialLoading
                ? 'Собираем топ блюд...'
                : summaryError && !summaryHasData
                  ? 'Топ блюд временно недоступен.'
                  : summaryDegraded
                    ? 'Показаны последние доступные данные по топу блюд.'
                    : pointId
                      ? `Идентификатор точки: ${formatId(pointId)}`
                      : 'Точка не выбрана'
            }
            tone={summaryError && !summaryHasData ? 'red' : 'default'}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <SectionCard
            title="Разбивка по каналам"
            subtitle="Сегодня по выбранной точке."
            extra={
              <Tag
                color="default"
                style={{
                  marginInlineEnd: 0,
                  background: channelsDegraded ? 'var(--j-warning-bg)' : 'var(--j-surface-panel)',
                  borderColor: channelsInitialLoading || channelsDegraded ? 'var(--j-border)' : 'var(--j-border-strong)',
                  color: channelsInitialLoading ? 'var(--j-text)' : channelsDegraded ? '#E8B86D' : '#FFD598',
                }}
              >
                {channelsInitialLoading ? 'ЗАГРУЗКА' : channelsDegraded ? 'ЧАСТИЧНО' : channelsError && !channelsHasData ? 'ОШИБКА' : 'ГОТОВО'}
              </Tag>
            }
          >
            {channelsInitialLoading ? (
              <SectionStateBlock
                title="Загружаем каналы точки"
                description="Смотрим текущий срез по каналам для выбранной точки."
              />
            ) : channelsError && !channelsHasData ? (
              <SectionStateBlock
                title="Каналы точки недоступны"
                description={getErrorMessage(channelsError)}
                action={
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={onRetryChannels}
                    style={{
                      background: 'var(--j-surface-high)',
                      color: 'var(--j-text)',
                      borderColor: 'var(--j-border-strong)',
                    }}
                  >
                    Повторить
                  </Button>
                }
              />
            ) : safeChannels.length > 0 ? (
              <Space direction="vertical" size={14} style={{ width: '100%' }}>
                {channelsDegraded ? (
                  <Typography.Text style={{ color: '#E8B86D', fontSize: 12 }}>
                    Показаны последние доступные данные по каналам точки.
                  </Typography.Text>
                ) : null}
                {safeChannels.map((channel) => (
                  <div
                    key={channel.source_channel}
                    style={{
                      padding: '12px 14px',
                      borderRadius: 10,
                      border: '1px solid var(--j-surface-high)',
                      background: 'var(--j-surface-muted)',
                    }}
                  >
                    <Space style={{ width: '100%', justifyContent: 'space-between' }} align="start">
                      <div>
                        <Typography.Text style={{ color: 'var(--j-text)' }}>
                          {channelLabel(channel.source_channel)}
                        </Typography.Text>
                        <Typography.Text
                          style={{ display: 'block', marginTop: 4, color: 'var(--j-text-tertiary)', fontSize: 12 }}
                        >
                          {formatMonoNumber(channel.order_count)} заказов
                        </Typography.Text>
                      </div>
                      <Typography.Text style={{ color: '#FFD598', fontFamily: '"JetBrains Mono", monospace' }}>
                        {formatMoney(channel.total_revenue)}
                      </Typography.Text>
                    </Space>
                    <div style={{ height: 8, marginTop: 10, borderRadius: 999, background: 'var(--j-surface-high)' }}>
                      <div
                        style={{
                          width: `${Math.max(8, (channel.order_count / maxChannelOrders) * 100)}%`,
                          height: '100%',
                          borderRadius: 999,
                          background: 'linear-gradient(90deg, #FFD598 0%, #E8B86D 100%)',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </Space>
            ) : (
              <SectionStateBlock
                title="Нет данных по каналам"
                description="Для выбранной точки данные по каналам пока не вернулись."
              />
            )}
          </SectionCard>
        </Col>

        <Col xs={24} xl={10}>
          <SectionCard
            title="Статус синхронизации"
            subtitle="Дашборд автоматически обновляется по событиям веб-сокета."
            extra={
              <Tag
                color="default"
                style={{
                  marginInlineEnd: 0,
                  background: 'var(--j-surface-high)',
                  borderColor: 'var(--j-border-strong)',
                  color: '#FFD598',
                }}
              >
                ОНЛАЙН
              </Tag>
            }
          >
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: 10,
                  border: '1px solid var(--j-surface-high)',
                  background: 'var(--j-surface-muted)',
                }}
              >
                <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 11, letterSpacing: '0.16em' }}>
                  Выбранная точка
                </Typography.Text>
                <Typography.Text
                  style={{
                    display: 'block',
                    marginTop: 8,
                    color: '#FFD598',
                    fontFamily: '"JetBrains Mono", monospace',
                    fontWeight: 600,
                  }}
                >
                  {pointName ?? (pointsLoading ? 'Загрузка точки...' : 'Точка не выбрана')}
                </Typography.Text>
              </div>

              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: 10,
                  border: '1px solid var(--j-surface-high)',
                  background: 'var(--j-surface-muted)',
                }}
              >
                <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 11, letterSpacing: '0.16em' }}>
                  Режим обновления
                </Typography.Text>
                <Typography.Text
                  style={{
                    display: 'block',
                    marginTop: 8,
                    color: 'var(--j-text)',
                  }}
                >
                  Обновления приходят по веб-сокету при создании заказа и смене статуса, резервный опрос включается каждые 30 секунд.
                </Typography.Text>
              </div>
            </Space>
          </SectionCard>
        </Col>
      </Row>
    </Space>
  );
}
