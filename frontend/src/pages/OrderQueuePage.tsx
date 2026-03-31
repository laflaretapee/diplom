import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from '../api/client';
import { useAuthStore } from '../auth/store';

// ─── Types ────────────────────────────────────────────────────────────────────

type OrderStatus = 'new' | 'in_progress' | 'ready' | 'delivered' | 'cancelled';

interface DragState {
  orderId: string;
  fromStatus: OrderStatus;
}

interface OrderItem {
  name?: string;
  quantity?: number;
  price?: number;
}

interface OrderRead {
  id: string;
  point_id: string;
  status: OrderStatus;
  items: OrderItem[];
  total_amount: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface PointRead {
  id: string;
  name: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const QUEUE_STATUSES: OrderStatus[] = ['new', 'in_progress', 'ready', 'delivered'];

const COLUMN_CONFIG: {
  status: OrderStatus;
  label: string;
  color: string;
  nextStatus: OrderStatus | null;
  nextLabel: string | null;
}[] = [
  { status: 'new', label: 'Новый', color: 'default', nextStatus: 'in_progress', nextLabel: 'В работу' },
  { status: 'in_progress', label: 'В работе', color: 'blue', nextStatus: 'ready', nextLabel: 'Готово' },
  { status: 'ready', label: 'Готов', color: 'green', nextStatus: 'delivered', nextLabel: 'Выдать' },
  { status: 'delivered', label: 'Выдан', color: 'cyan', nextStatus: null, nextLabel: null },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function authHeader(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function extractErrorMessage(error: unknown, fallback: string): string {
  const maybeError = error as {
    response?: { status?: number; data?: { detail?: unknown } };
    message?: unknown;
  };
  const status = maybeError.response?.status;
  const detail = maybeError.response?.data?.detail;
  if (status === 403) {
    return 'Недостаточно прав для изменения статуса заказа.';
  }

  if (status === 404) {
    return 'Заказ не найден.';
  }

  if (status === 422) {
    return 'Этот переход статуса сейчас недоступен.';
  }

  if (typeof detail === 'string' && /[А-Яа-яЁё]/.test(detail) && detail.trim()) {
    return detail;
  }

  const message = maybeError.message;
  if (typeof message === 'string' && /[А-Яа-яЁё]/.test(message) && message.trim()) {
    return message;
  }

  return fallback;
}

type WsConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error';

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

function formatAmount(amount: string): string {
  return `${Number(amount).toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₽`;
}

function getNextQueueStatus(status: OrderStatus): OrderStatus | null {
  const column = COLUMN_CONFIG.find((item) => item.status === status);
  return column?.nextStatus ?? null;
}

function canDropToStatus(fromStatus: OrderStatus, toStatus: OrderStatus): boolean {
  return getNextQueueStatus(fromStatus) === toStatus;
}

// ─── API ──────────────────────────────────────────────────────────────────────

async function fetchPoints(token: string | null): Promise<PointRead[]> {
  const { data } = await apiClient.get<PointRead[]>('/v1/points', {
    headers: authHeader(token),
  });
  return Array.isArray(data) ? data : [];
}

async function fetchQueueOrders(pointId: string, token: string | null): Promise<OrderRead[]> {
  // Fetch all statuses that belong in the queue (no status filter = all orders)
  // Then filter client-side to exclude 'cancelled'
  const { data } = await apiClient.get<OrderRead[]>('/v1/orders', {
    headers: authHeader(token),
    params: { point_id: pointId },
  });
  const orders = Array.isArray(data) ? data : [];
  return orders.filter((o) => QUEUE_STATUSES.includes(o.status));
}

async function updateOrderStatus(
  orderId: string,
  newStatus: OrderStatus,
  token: string | null,
): Promise<void> {
  await apiClient.patch(
    `/v1/orders/${orderId}/status`,
    { status: newStatus },
    { headers: authHeader(token) },
  );
}

// ─── Order Card ───────────────────────────────────────────────────────────────

interface OrderCardProps {
  order: OrderRead;
  nextStatus: OrderStatus | null;
  nextLabel: string | null;
  onStatusChange: (orderId: string, status: OrderStatus) => Promise<void>;
  loading: boolean;
  draggable?: boolean;
  isDragging?: boolean;
  onDragStart?: (order: OrderRead) => void;
  onDragEnd?: () => void;
}

function OrderCard({
  order,
  nextStatus,
  nextLabel,
  onStatusChange,
  loading,
  draggable = false,
  isDragging = false,
  onDragStart,
  onDragEnd,
}: OrderCardProps) {
  const itemCount = Array.isArray(order.items) ? order.items.length : 0;

  return (
    <Card
      size="small"
      draggable={draggable}
      onDragStart={(event) => {
        if (!draggable) {
          return;
        }
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', order.id);
        onDragStart?.(order);
      }}
      onDragEnd={() => onDragEnd?.()}
      style={{
        marginBottom: 8,
        borderRadius: 8,
        cursor: draggable ? (loading ? 'progress' : 'grab') : 'default',
        opacity: isDragging ? 0.55 : 1,
        border: isDragging ? '1px solid #1677ff' : undefined,
        boxShadow: isDragging ? '0 10px 24px rgba(22, 119, 255, 0.14)' : undefined,
        transition: 'opacity 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease',
      }}
      styles={{ body: { padding: '10px 12px' } }}
    >
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text strong style={{ fontFamily: 'monospace', fontSize: 13 }}>
            #{order.id.slice(0, 8).toUpperCase()}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {formatTime(order.created_at)}
          </Typography.Text>
        </Space>
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {itemCount} {itemCount === 1 ? 'позиция' : itemCount < 5 ? 'позиции' : 'позиций'}
          </Typography.Text>
          <Typography.Text strong style={{ fontSize: 13 }}>
            {formatAmount(order.total_amount)}
          </Typography.Text>
        </Space>
        {nextStatus !== null && nextLabel !== null && (
          <Button
            type="primary"
            size="small"
            block
            loading={loading}
            onClick={() => { void onStatusChange(order.id, nextStatus!); }}
            style={{ marginTop: 4 }}
          >
            {nextLabel}
          </Button>
        )}
      </Space>
    </Card>
  );
}

// ─── Kanban Column ────────────────────────────────────────────────────────────

interface KanbanColumnProps {
  status: OrderStatus;
  label: string;
  color: string;
  nextStatus: OrderStatus | null;
  nextLabel: string | null;
  orders: OrderRead[];
  onStatusChange: (orderId: string, status: OrderStatus) => Promise<void>;
  pendingOrderIds: string[];
  emptyDescription: string;
  dragState: DragState | null;
  isDropAllowed: boolean;
  isDropHovered: boolean;
  isInvalidDropHovered: boolean;
  onCardDragStart: (order: OrderRead) => void;
  onCardDragEnd: () => void;
  onColumnDragEnter: (status: OrderStatus, valid: boolean) => void;
  onColumnDragLeave: (status: OrderStatus) => void;
  onColumnDrop: (status: OrderStatus) => void;
}

function KanbanColumn({
  status,
  label,
  color,
  nextStatus,
  nextLabel,
  orders,
  onStatusChange,
  pendingOrderIds,
  emptyDescription,
  dragState,
  isDropAllowed,
  isDropHovered,
  isInvalidDropHovered,
  onCardDragStart,
  onCardDragEnd,
  onColumnDragEnter,
  onColumnDragLeave,
  onColumnDrop,
}: KanbanColumnProps) {
  const columnStyle = {
    background: isDropHovered ? '#e6f4ff' : isInvalidDropHovered ? '#fff2f0' : '#f5f5f5',
    borderRadius: 10,
    padding: '10px 8px',
    minHeight: 200,
    flex: 1,
    minWidth: 0,
    border: isDropHovered
      ? '2px dashed #1677ff'
      : isInvalidDropHovered
        ? '2px dashed #ff4d4f'
        : '2px dashed transparent',
    boxShadow: isDropHovered ? 'inset 0 0 0 1px rgba(22, 119, 255, 0.08)' : undefined,
    transition: 'background 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease',
  } satisfies React.CSSProperties;

  return (
    <div
      style={columnStyle}
      onDragOver={(event) => {
        if (!dragState) {
          return;
        }
        if (isDropAllowed) {
          event.preventDefault();
          event.dataTransfer.dropEffect = 'move';
        } else {
          event.dataTransfer.dropEffect = 'none';
        }
      }}
      onDragEnter={() => {
        if (!dragState) {
          return;
        }
        onColumnDragEnter(status, isDropAllowed);
      }}
      onDragLeave={(event) => {
        const nextTarget = event.relatedTarget;
        if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
          return;
        }
        onColumnDragLeave(status);
      }}
      onDrop={(event) => {
        if (!dragState) {
          return;
        }
        event.preventDefault();
        onColumnDrop(status);
      }}
    >
      <Space style={{ marginBottom: 10, width: '100%', justifyContent: 'space-between' }}>
        <Tag color={color} style={{ fontSize: 13, padding: '2px 10px' }}>
          {label}
        </Tag>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {orders.length}
        </Typography.Text>
      </Space>
      {orders.length === 0 ? (
        <Empty
          description={emptyDescription}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ margin: '16px 0' }}
        />
      ) : (
        orders.map((order) => (
          <OrderCard
            key={order.id}
            order={order}
            nextStatus={nextStatus}
            nextLabel={nextLabel}
            onStatusChange={onStatusChange}
            loading={pendingOrderIds.includes(order.id)}
            draggable={!pendingOrderIds.includes(order.id) && nextStatus !== null}
            isDragging={dragState?.orderId === order.id}
            onDragStart={onCardDragStart}
            onDragEnd={onCardDragEnd}
          />
        ))
      )}
    </div>
  );
}

// ─── WebSocket hook ───────────────────────────────────────────────────────────

function useOrderQueueWS(
  pointId: string | null,
  token: string | null,
  onEvent: () => void,
) {
  const [status, setStatus] = useState<WsConnectionState>('idle');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    if (!pointId || !token) {
      setStatus('idle');
      return;
    }

    setStatus((current) => (current === 'connected' ? 'connected' : 'connecting'));

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = import.meta.env.VITE_WS_HOST ?? window.location.hostname + ':18000';
    const url = `${protocol}://${host}/api/v1/ws/orders/${pointId}?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as { type: string };
        if (msg.type === 'order_created' || msg.type === 'order_status_changed') {
          onEventRef.current();
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      setStatus('reconnecting');
      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, 5000);
    };

    ws.onerror = () => {
      setStatus('error');
      ws.close();
    };
  }, [pointId, token]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return status;
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function OrderQueuePage() {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();

  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);
  const [pendingOrderIds, setPendingOrderIds] = useState<string[]>([]);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [dropTargetStatus, setDropTargetStatus] = useState<OrderStatus | null>(null);
  const [invalidDropStatus, setInvalidDropStatus] = useState<OrderStatus | null>(null);
  const pendingOrderIdsRef = useRef<string[]>([]);

  useEffect(() => {
    pendingOrderIdsRef.current = pendingOrderIds;
  }, [pendingOrderIds]);

  // Fetch points
  const {
    data: points = [],
    isLoading: pointsLoading,
    isError: pointsError,
    refetch: refetchPoints,
  } = useQuery({
    queryKey: ['queue-points', token],
    queryFn: () => fetchPoints(token),
    retry: false,
    select: (data) => (Array.isArray(data) ? data : []),
  });

  // Auto-select first point
  useEffect(() => {
    if (points.length > 0 && selectedPointId === null) {
      setSelectedPointId(points[0].id);
    }
  }, [points, selectedPointId]);

  // Invalidate on WS event
  const handleWsEvent = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['queue-orders', selectedPointId] });
  }, [queryClient, selectedPointId]);

  const wsStatus = useOrderQueueWS(selectedPointId, token, handleWsEvent);

  // Fetch queue orders with polling fallback (30s)
  const {
    data: orders = [],
    isLoading: ordersLoading,
    isFetching: ordersFetching,
    isError: ordersError,
    refetch: refetchOrders,
  } = useQuery({
    queryKey: ['queue-orders', selectedPointId],
    queryFn: () => (selectedPointId ? fetchQueueOrders(selectedPointId, token) : Promise.resolve([])),
    enabled: selectedPointId !== null,
    refetchInterval: 30_000,
    retry: false,
    select: (data) => (Array.isArray(data) ? data : []),
  });

  const handleStatusChange = useCallback(async (orderId: string, newStatus: OrderStatus) => {
    if (pendingOrderIdsRef.current.includes(orderId)) {
      return;
    }
    setPendingOrderIds((current) => (current.includes(orderId) ? current : [...current, orderId]));
    setMutationError(null);
    try {
      await updateOrderStatus(orderId, newStatus, token);
      queryClient.setQueryData<OrderRead[]>(
        ['queue-orders', selectedPointId],
        (current) =>
          Array.isArray(current)
            ? current.map((order) =>
                order.id === orderId
                  ? {
                      ...order,
                      status: newStatus,
                      updated_at: new Date().toISOString(),
                    }
                  : order,
              )
            : current,
      );
      void queryClient.invalidateQueries({ queryKey: ['queue-orders', selectedPointId] });
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
    } catch (error) {
      setMutationError(
        extractErrorMessage(error, 'Не удалось изменить статус заказа. Повторите попытку.'),
      );
    } finally {
      setPendingOrderIds((current) => current.filter((item) => item !== orderId));
    }
  }, [queryClient, selectedPointId, token]);

  const resetDragState = useCallback(() => {
    setDragState(null);
    setDropTargetStatus(null);
    setInvalidDropStatus(null);
  }, []);

  useEffect(() => {
    if (!dragState) {
      return;
    }

    const currentOrder = orders.find((order) => order.id === dragState.orderId);
    if (!currentOrder || currentOrder.status !== dragState.fromStatus) {
      resetDragState();
    }
  }, [dragState, orders, resetDragState]);

  const handleCardDragStart = useCallback((order: OrderRead) => {
    setMutationError(null);
    setDragState({ orderId: order.id, fromStatus: order.status });
    setDropTargetStatus(null);
    setInvalidDropStatus(null);
  }, []);

  const handleColumnDragEnter = useCallback((status: OrderStatus, valid: boolean) => {
    if (valid) {
      setDropTargetStatus(status);
      setInvalidDropStatus(null);
      return;
    }
    setDropTargetStatus(null);
    setInvalidDropStatus(status);
  }, []);

  const handleColumnDragLeave = useCallback((status: OrderStatus) => {
    setDropTargetStatus((current) => (current === status ? null : current));
    setInvalidDropStatus((current) => (current === status ? null : current));
  }, []);

  const handleColumnDrop = useCallback(async (status: OrderStatus) => {
    if (!dragState) {
      return;
    }

    const currentOrder = orders.find((order) => order.id === dragState.orderId);
    const currentStatus = currentOrder?.status;
    const draggedOrderId = dragState.orderId;
    resetDragState();

    if (!currentOrder || currentStatus !== dragState.fromStatus) {
      setMutationError('Очередь обновилась. Перетащите карточку ещё раз из актуальной колонки.');
      return;
    }

    const isAllowed = canDropToStatus(currentStatus, status);
    if (!isAllowed) {
      return;
    }

    await handleStatusChange(draggedOrderId, status);
  }, [dragState, handleStatusChange, orders, resetDragState]);

  const pointOptions = points.map((p) => ({ value: p.id, label: p.name }));
  const liveSyncAlert =
    wsStatus === 'connected'
      ? null
      : {
          type: wsStatus === 'error' || wsStatus === 'reconnecting' ? ('warning' as const) : ('info' as const),
          message:
            wsStatus === 'error' || wsStatus === 'reconnecting'
              ? 'Режим реального времени недоступен'
              : 'Подключаемся к обновлениям очереди',
          description:
            wsStatus === 'error' || wsStatus === 'reconnecting'
              ? 'Список обновляется автоматически каждые 30 секунд.'
              : 'Как только соединение установится, список будет обновляться без перезагрузки.',
        };

  const ordersByStatus = (status: OrderStatus): OrderRead[] =>
    orders.filter((o) => o.status === status);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Row justify="space-between" align="middle" gutter={[8, 8]}>
        <Col>
          <Typography.Title level={3} style={{ marginBottom: 0 }}>
            Очередь заказов
          </Typography.Title>
        </Col>
        <Col xs={24} sm={12} md={8} lg={6}>
          <Select
            placeholder="Выберите точку"
            style={{ width: '100%' }}
            options={pointOptions}
            value={selectedPointId ?? undefined}
            onChange={(val: string) => setSelectedPointId(val)}
            loading={pointsLoading}
            notFoundContent={pointsError ? 'Не удалось загрузить точки' : 'Нет доступных точек'}
          />
        </Col>
      </Row>

      {mutationError ? (
        <Alert type="error" showIcon message="Не удалось изменить статус заказа" description={mutationError} />
      ) : null}

      {liveSyncAlert ? (
        <Alert type={liveSyncAlert.type} showIcon message={liveSyncAlert.message} description={liveSyncAlert.description} />
      ) : null}

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

      {ordersError ? (
        <Alert
          type="error"
          showIcon
          message="Не удалось загрузить очередь заказов"
          description="Список не обновился. Повторите запрос или дождитесь следующей автоматической синхронизации."
          action={
            <Button size="small" onClick={() => void refetchOrders()}>
              Повторить
            </Button>
          }
        />
      ) : null}

      {selectedPointId === null ? (
        <Card>
          {pointsLoading ? (
            <Spin tip="Загружаем точки..." style={{ display: 'block', padding: '32px 0' }} />
          ) : (
            <Empty
              description={
                points.length === 0
                  ? 'Нет доступных точек для отображения очереди'
                  : 'Выберите точку, чтобы увидеть очередь заказов'
              }
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Card>
      ) : ordersLoading ? (
        <Card>
          <Spin tip="Загрузка заказов..." style={{ display: 'block', padding: '32px 0' }} />
        </Card>
      ) : (
        <>
          <Space
            style={{
              width: '100%',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
          <Typography.Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
            На компьютере карточки можно перетаскивать только в следующую допустимую колонку. Кнопки ниже остаются резервным сценарием.
          </Typography.Text>
            {ordersFetching ? (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Синхронизация очереди...
              </Typography.Text>
            ) : null}
          </Space>
          {/* Kanban board */}
          <div
            style={{
              display: 'flex',
              gap: 10,
              overflowX: 'auto',
              paddingBottom: 8,
              // mobile: flex-wrap
              flexWrap: 'nowrap',
            }}
            className="kanban-board"
          >
            {COLUMN_CONFIG.map((col) => (
              <KanbanColumn
                key={col.status}
                status={col.status}
                label={col.label}
                color={col.color}
                nextStatus={col.nextStatus}
                nextLabel={col.nextLabel}
                orders={ordersByStatus(col.status)}
                onStatusChange={handleStatusChange}
                pendingOrderIds={pendingOrderIds}
                emptyDescription={`В колонке «${col.label}» пока нет заказов`}
                dragState={dragState}
                isDropAllowed={dragState ? canDropToStatus(dragState.fromStatus, col.status) : false}
                isDropHovered={dropTargetStatus === col.status}
                isInvalidDropHovered={invalidDropStatus === col.status}
                onCardDragStart={handleCardDragStart}
                onCardDragEnd={resetDragState}
                onColumnDragEnter={handleColumnDragEnter}
                onColumnDragLeave={handleColumnDragLeave}
                onColumnDrop={(status) => { void handleColumnDrop(status); }}
              />
            ))}
          </div>
        </>
      )}

      <style>{`
        @media (max-width: 767px) {
          .kanban-board {
            flex-direction: column !important;
          }
        }
      `}</style>
    </Space>
  );
}
