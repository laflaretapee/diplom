import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useQuery, useQueryClient } from '@tanstack/react-query';
// dayjs is a peer dependency of antd and is always available in the node_modules
// eslint-disable-next-line import/no-extraneous-dependencies
import dayjs, { type Dayjs } from 'dayjs';

import { apiClient } from '../api/client';
import { useAuthStore } from '../auth/store';

// ─── Types ────────────────────────────────────────────────────────────────────

type OrderStatus = 'new' | 'in_progress' | 'ready' | 'delivered' | 'cancelled';
type PaymentType = 'cash' | 'card' | 'online';
type PaymentStatus = 'pending' | 'paid' | 'failed' | 'refunded';
type SourceChannel = 'website' | 'mobile_app' | 'telegram' | 'vk' | 'pos';

interface OrderRead {
  id: string;
  point_id: string;
  status: OrderStatus;
  payment_type: PaymentType;
  payment_status: PaymentStatus;
  source_channel: SourceChannel;
  items: unknown[];
  total_amount: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface PointRead {
  id: string;
  name: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<OrderStatus, string> = {
  new: 'Новый',
  in_progress: 'В процессе',
  ready: 'Готов',
  delivered: 'Доставлен',
  cancelled: 'Отменён',
};

const STATUS_COLORS: Record<OrderStatus, string> = {
  new: 'default',
  in_progress: 'blue',
  ready: 'green',
  delivered: 'cyan',
  cancelled: 'red',
};

const CHANNEL_LABELS: Record<SourceChannel, string> = {
  website: 'Сайт',
  mobile_app: 'Приложение',
  telegram: 'Телеграм',
  vk: 'ВКонтакте',
  pos: 'Касса',
};

const PAYMENT_LABELS: Record<PaymentType, string> = {
  cash: 'Наличные',
  card: 'Карта',
  online: 'Онлайн',
};

function authHeader(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

type WsConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error';

// ─── API fetchers ─────────────────────────────────────────────────────────────

async function fetchPoints(token: string | null): Promise<PointRead[]> {
  const { data } = await apiClient.get<PointRead[]>('/v1/points', {
    headers: authHeader(token),
  });
  return data;
}

interface OrderFilters {
  point_id: string;
  status?: OrderStatus;
  date_from?: string;
  date_to?: string;
}

async function fetchOrders(
  filters: OrderFilters,
  token: string | null,
): Promise<OrderRead[]> {
  const params: Record<string, string> = { point_id: filters.point_id };
  if (filters.status) params['order_status'] = filters.status;
  if (filters.date_from) params['date_from'] = filters.date_from;
  if (filters.date_to) params['date_to'] = filters.date_to;

  const { data } = await apiClient.get<OrderRead[]>('/v1/orders', {
    headers: authHeader(token),
    params,
  });
  return data;
}

function useOrderHistoryWS(
  pointId: string | null,
  token: string | null,
  enabled: boolean,
  onEvent: () => void,
) {
  const [status, setStatus] = useState<WsConnectionState>('idle');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!enabled || !pointId || !token) {
      setStatus('idle');
      return undefined;
    }

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;

      setStatus((current) => (current === 'connected' ? 'connected' : 'connecting'));

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = import.meta.env.VITE_WS_HOST ?? `${window.location.hostname}:18000`;
      const url = `${protocol}://${host}/api/v1/ws/orders/${pointId}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data as string) as { type?: string };
          if (msg.type === 'order_created' || msg.type === 'order_status_changed') {
            onEventRef.current();
          }
        } catch {
          // Ignore malformed events and keep the connection alive.
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (cancelled) return;
        setStatus('reconnecting');
        reconnectTimerRef.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        setStatus('error');
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

  return status;
}

// ─── Component ────────────────────────────────────────────────────────────────

const STATUS_OPTIONS = [
  { value: '', label: 'Все статусы' },
  { value: 'new', label: STATUS_LABELS.new },
  { value: 'in_progress', label: STATUS_LABELS.in_progress },
  { value: 'ready', label: STATUS_LABELS.ready },
  { value: 'delivered', label: STATUS_LABELS.delivered },
  { value: 'cancelled', label: STATUS_LABELS.cancelled },
];

export function OrderHistoryPage() {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();

  // Filter state
  const [selectedPointId, setSelectedPointId] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<Dayjs | null>(null);
  const [dateTo, setDateTo] = useState<Dayjs | null>(null);

  // Applied filters (only update on "Применить" click)
  const [appliedFilters, setAppliedFilters] = useState<OrderFilters | null>(null);

  // Fetch points list
  const {
    data: points = [],
    isLoading: pointsLoading,
    isError: pointsError,
    refetch: refetchPoints,
  } = useQuery({
    queryKey: ['order-history-points', token],
    queryFn: () => fetchPoints(token),
    retry: false,
    select: (data) => (Array.isArray(data) ? data : []),
  });

  // Fetch orders only when filters are applied
  const {
    data: orders = [],
    isLoading: ordersLoading,
    isError: ordersError,
    isFetching: ordersFetching,
    refetch: refetchOrders,
  } = useQuery({
    queryKey: ['orders', appliedFilters],
    queryFn: () => (appliedFilters ? fetchOrders(appliedFilters, token) : Promise.resolve([])),
    enabled: appliedFilters !== null,
    retry: false,
    refetchInterval: appliedFilters ? 30_000 : false,
  });

  const wsStatus = useOrderHistoryWS(
    appliedFilters?.point_id ?? null,
    token,
    appliedFilters !== null,
    () => {
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  );

  const handleApply = () => {
    if (!selectedPointId) return;
    const filters: OrderFilters = { point_id: selectedPointId };
    if (selectedStatus) filters.status = selectedStatus as OrderStatus;
    if (dateFrom) filters.date_from = dateFrom.format('YYYY-MM-DD');
    if (dateTo) filters.date_to = dateTo.format('YYYY-MM-DD');
    setAppliedFilters(filters);
  };

  const pointOptions = points.map((p) => ({ value: p.id, label: p.name }));
  const wsAlert =
    wsStatus === 'error' || wsStatus === 'reconnecting'
      ? {
          type: 'warning' as const,
          message: 'Нет связи с обновлениями в реальном времени',
          description: 'История обновляется автоматически каждые 30 секунд.',
        }
      : wsStatus === 'connecting'
        ? {
            type: 'info' as const,
            message: 'Подключаемся к обновлениям истории',
            description: 'Как только соединение установится, список будет обновляться без перезагрузки.',
          }
        : null;

  const columns: ColumnsType<OrderRead> = [
    {
      title: '#',
      dataIndex: 'id',
      key: 'id',
      width: 80,
      render: (id: string) => id.slice(0, 8).toUpperCase(),
    },
    {
      title: 'Дата',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => dayjs(val).format('DD.MM.YYYY HH:mm'),
    },
    {
      title: 'Точка',
      dataIndex: 'point_id',
      key: 'point_id',
      render: (pid: string) => {
        const point = points.find((p) => p.id === pid);
        return point ? point.name : pid.slice(0, 8);
      },
    },
    {
      title: 'Канал',
      dataIndex: 'source_channel',
      key: 'source_channel',
      render: (channel: SourceChannel) => CHANNEL_LABELS[channel] ?? channel,
    },
    {
      title: 'Оплата',
      dataIndex: 'payment_type',
      key: 'payment_type',
      render: (type: PaymentType) => PAYMENT_LABELS[type] ?? type,
    },
    {
      title: 'Сумма',
      dataIndex: 'total_amount',
      key: 'total_amount',
      align: 'right',
      render: (amount: string) =>
        `${Number(amount).toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽`,
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: OrderStatus) => (
        <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status] ?? status}</Tag>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ marginBottom: 0 }}>
        История заказов
      </Typography.Title>

      {pointsError ? (
        <Alert
          type="error"
          showIcon
          message="Не удалось загрузить точки"
          description="Проверьте соединение и повторите попытку."
          action={
            <Button size="small" onClick={() => void refetchPoints()}>
              Повторить
            </Button>
          }
        />
      ) : null}

      {/* Filters */}
      <Card>
        <Row gutter={[16, 16]} align="bottom">
          <Col xs={24} sm={12} md={6}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Text>Точка</Typography.Text>
              <Select
                placeholder="Выберите точку"
                style={{ width: '100%' }}
                options={pointOptions}
                value={selectedPointId || undefined}
                onChange={(val: string) => setSelectedPointId(val)}
                loading={pointsLoading}
                notFoundContent={pointsError ? 'Не удалось загрузить точки' : 'Нет доступных точек'}
              />
            </Space>
          </Col>

          <Col xs={24} sm={12} md={6}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Text>Статус</Typography.Text>
              <Select
                style={{ width: '100%' }}
                options={STATUS_OPTIONS}
                value={selectedStatus}
                onChange={(val: string) => setSelectedStatus(val)}
              />
            </Space>
          </Col>

          <Col xs={24} sm={12} md={4}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Text>Дата с</Typography.Text>
              <DatePicker
                style={{ width: '100%' }}
                value={dateFrom}
                onChange={(val) => setDateFrom(val)}
                format="DD.MM.YYYY"
                placeholder="дд.мм.гггг"
              />
            </Space>
          </Col>

          <Col xs={24} sm={12} md={4}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Text>Дата по</Typography.Text>
              <DatePicker
                style={{ width: '100%' }}
                value={dateTo}
                onChange={(val) => setDateTo(val)}
                format="DD.MM.YYYY"
                placeholder="дд.мм.гггг"
              />
            </Space>
          </Col>

          <Col xs={24} sm={12} md={4}>
            <Button
              type="primary"
              onClick={handleApply}
              disabled={!selectedPointId}
              block
            >
              Применить
            </Button>
          </Col>
        </Row>
      </Card>

      {wsAlert ? (
        <Alert
          type={wsAlert.type}
          showIcon
          message={wsAlert.message}
          description={wsAlert.description}
        />
      ) : null}

      {/* Orders table */}
      <Card>
        {ordersError ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert
              type="error"
              showIcon
              message="Не удалось загрузить историю заказов"
              description="Список не обновился. Проверьте соединение и повторите запрос."
              action={
                <Button size="small" onClick={() => void refetchOrders()}>
                  Повторить
                </Button>
              }
            />
          </Space>
        ) : (
          <Spin spinning={ordersLoading || ordersFetching}>
            <Table<OrderRead>
              rowKey="id"
              columns={columns}
              dataSource={appliedFilters ? orders : []}
              locale={{
                emptyText: appliedFilters ? (
                  <Empty description="Заказов по выбранным фильтрам не найдено" />
                ) : (
                  <Empty description="Выберите точку и нажмите «Применить», чтобы увидеть историю" />
                ),
              }}
              pagination={{ pageSize: 20 }}
            />
          </Spin>
        )}
      </Card>
    </Space>
  );
}
