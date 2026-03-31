import {
  closestCorners,
  DndContext,
  type DragEndEvent,
  useDraggable,
  useDroppable,
} from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import {
  CalendarOutlined,
  CommentOutlined,
  PaperClipOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Badge,
  Button,
  Card,
  DatePicker,
  Drawer,
  Form,
  Input,
  List,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { apiClient } from '../api/client';

type BoardColumn = {
  id: string;
  board_id: string;
  name: string;
  position: number;
  color: string | null;
  created_at: string;
};

type BoardDetail = {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
  columns: BoardColumn[];
  custom_fields: CustomFieldItem[];
};

type CardItem = {
  id: string;
  board_id: string;
  column_id: string;
  title: string;
  description: string | null;
  assignee_id: string | null;
  deadline: string | null;
  priority: string;
  tags: string[];
  position: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};

type CardsByColumn = Record<string, CardItem[]>;

type CommentItem = {
  id: string;
  card_id: string;
  author_id: string;
  body: string;
  created_at: string;
};

type HistoryItem = {
  id: string;
  card_id: string;
  from_column_id: string | null;
  to_column_id: string;
  changed_by: string;
  changed_at: string;
};

type AttachmentItem = {
  id: string;
  original_filename: string;
  file_path: string;
  mime_type: string;
  created_at: string;
};

type CustomFieldItem = {
  id: string;
  board_id: string;
  name: string;
  field_type: string;
  options: Record<string, unknown> | null;
  position: number;
};

type UserOption = {
  id: string;
  name: string;
};

type ColumnFormValues = {
  name: string;
  color?: string;
};

type CardFormValues = {
  title: string;
};

type CardDetailsFormValues = {
  title: string;
  description?: string;
  priority: string;
  assignee_id?: string;
  deadline?: dayjs.Dayjs;
  tags?: string[];
};

function DraggableCard(props: {
  card: CardItem;
  onOpen: (card: CardItem) => void;
}) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: `card:${props.card.id}`,
    data: props.card,
  });

  return (
    <Card
      ref={setNodeRef}
      size="small"
      onClick={() => props.onOpen(props.card)}
      style={{
        transform: CSS.Translate.toString(transform),
        cursor: 'grab',
        marginBottom: 12,
      }}
      {...listeners}
      {...attributes}
    >
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Typography.Text strong>{props.card.title}</Typography.Text>
        <Space wrap size={[8, 8]}>
          <Tag color={priorityColor(props.card.priority)}>{props.card.priority}</Tag>
          {props.card.deadline ? (
            <Tag icon={<CalendarOutlined />}>{dayjs(props.card.deadline).format('DD.MM')}</Tag>
          ) : null}
          {props.card.tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Space>
      </Space>
    </Card>
  );
}

function DroppableColumn(props: {
  column: BoardColumn;
  cards: CardItem[];
  onOpenCard: (card: CardItem) => void;
  onCreateCard: (columnId: string) => void;
}) {
  const { setNodeRef } = useDroppable({
    id: `column:${props.column.id}`,
    data: { columnId: props.column.id },
  });

  return (
    <div
      ref={setNodeRef}
      style={{
        minWidth: 300,
        background: 'rgba(19, 19, 19, 0.75)',
        border: '1px solid rgba(79, 69, 56, 0.35)',
        borderRadius: 18,
        padding: 16,
      }}
    >
      <Space
        style={{
          width: '100%',
          justifyContent: 'space-between',
          borderLeft: `4px solid ${props.column.color || '#1890ff'}`,
          paddingLeft: 12,
          marginBottom: 16,
        }}
      >
        <Space>
          <Typography.Text strong style={{ color: '#F5F2ED' }}>
            {props.column.name}
          </Typography.Text>
          <Badge count={props.cards.length} />
        </Space>
        <Button
          size="small"
          icon={<PlusOutlined />}
          onClick={() => props.onCreateCard(props.column.id)}
        >
          Карточка
        </Button>
      </Space>
      {props.cards.map((card) => (
        <DraggableCard key={card.id} card={card} onOpen={props.onOpenCard} />
      ))}
    </div>
  );
}

function priorityColor(priority: string): string {
  if (priority === 'urgent') {
    return 'red';
  }
  if (priority === 'high') {
    return 'orange';
  }
  if (priority === 'low') {
    return 'blue';
  }
  return 'gold';
}

async function fetchBoard(boardId: string): Promise<BoardDetail> {
  const { data } = await apiClient.get<BoardDetail>(`/v1/kanban/boards/${boardId}`);
  return data;
}

async function fetchCards(boardId: string): Promise<CardsByColumn> {
  const { data } = await apiClient.get<CardsByColumn>(`/v1/kanban/boards/${boardId}/cards`);
  return data;
}

export function KanbanBoardPage() {
  const params = useParams<{ boardId: string }>();
  const boardId = params.boardId ?? '';
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [cardsState, setCardsState] = useState<CardsByColumn>({});
  const [isColumnModalOpen, setIsColumnModalOpen] = useState(false);
  const [createCardColumnId, setCreateCardColumnId] = useState<string | null>(null);
  const [selectedCard, setSelectedCard] = useState<CardItem | null>(null);
  const [commentBody, setCommentBody] = useState('');
  const [customFieldDrafts, setCustomFieldDrafts] = useState<Record<string, string>>({});
  const [columnForm] = Form.useForm<ColumnFormValues>();
  const [cardForm] = Form.useForm<CardFormValues>();
  const [detailsForm] = Form.useForm<CardDetailsFormValues>();
  const watchedTitle = Form.useWatch('title', detailsForm);

  const boardQuery = useQuery({
    queryKey: ['kanban-board', boardId],
    queryFn: () => fetchBoard(boardId),
    enabled: Boolean(boardId),
  });

  const cardsQuery = useQuery({
    queryKey: ['kanban-cards', boardId],
    queryFn: () => fetchCards(boardId),
    enabled: Boolean(boardId),
  });

  const usersQuery = useQuery({
    queryKey: ['kanban-users'],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get<UserOption[]>('/v1/users');
        return data;
      } catch {
        return [];
      }
    },
  });

  const commentsQuery = useQuery({
    queryKey: ['kanban-comments', selectedCard?.id],
    queryFn: async () => {
      const { data } = await apiClient.get<CommentItem[]>(
        `/v1/kanban/cards/${selectedCard?.id}/comments`,
      );
      return data;
    },
    enabled: Boolean(selectedCard),
  });

  const historyQuery = useQuery({
    queryKey: ['kanban-history', selectedCard?.id],
    queryFn: async () => {
      const { data } = await apiClient.get<HistoryItem[]>(
        `/v1/kanban/cards/${selectedCard?.id}/history`,
      );
      return data;
    },
    enabled: Boolean(selectedCard),
  });

  const attachmentsQuery = useQuery({
    queryKey: ['kanban-attachments', selectedCard?.id],
    queryFn: async () => {
      const { data } = await apiClient.get<AttachmentItem[]>(
        `/v1/kanban/cards/${selectedCard?.id}/attachments`,
      );
      return data;
    },
    enabled: Boolean(selectedCard),
  });

  useEffect(() => {
    if (cardsQuery.data) {
      setCardsState(cardsQuery.data);
    }
  }, [cardsQuery.data]);

  useEffect(() => {
    if (!selectedCard) {
      detailsForm.resetFields();
      setCustomFieldDrafts({});
      return;
    }

    detailsForm.setFieldsValue({
      title: selectedCard.title,
      description: selectedCard.description ?? undefined,
      priority: selectedCard.priority,
      assignee_id: selectedCard.assignee_id ?? undefined,
      deadline: selectedCard.deadline ? dayjs(selectedCard.deadline) : undefined,
      tags: selectedCard.tags,
    });
  }, [detailsForm, selectedCard]);

  const refreshBoard = async () => {
    await queryClient.invalidateQueries({ queryKey: ['kanban-board', boardId] });
    await queryClient.invalidateQueries({ queryKey: ['kanban-cards', boardId] });
    if (selectedCard) {
      await queryClient.invalidateQueries({ queryKey: ['kanban-comments', selectedCard.id] });
      await queryClient.invalidateQueries({ queryKey: ['kanban-history', selectedCard.id] });
      await queryClient.invalidateQueries({ queryKey: ['kanban-attachments', selectedCard.id] });
    }
  };

  const createColumn = useMutation({
    mutationFn: async (values: ColumnFormValues) => {
      const { data } = await apiClient.post<BoardColumn>(`/v1/kanban/boards/${boardId}/columns`, {
        name: values.name,
        color: values.color,
      });
      return data;
    },
    onSuccess: async () => {
      await refreshBoard();
      setIsColumnModalOpen(false);
      columnForm.resetFields();
      messageApi.success('Колонка создана');
    },
    onError: () => messageApi.error('Не удалось создать колонку'),
  });

  const createCard = useMutation({
    mutationFn: async (values: CardFormValues) => {
      const { data } = await apiClient.post<CardItem>(
        `/v1/kanban/columns/${createCardColumnId}/cards`,
        { title: values.title },
      );
      return data;
    },
    onSuccess: async () => {
      await refreshBoard();
      setCreateCardColumnId(null);
      cardForm.resetFields();
      messageApi.success('Карточка создана');
    },
    onError: () => messageApi.error('Не удалось создать карточку'),
  });

  const moveCard = useMutation({
    mutationFn: async (payload: { cardId: string; column_id: string; position: number }) => {
      await apiClient.put(`/v1/kanban/cards/${payload.cardId}/move`, {
        column_id: payload.column_id,
        position: payload.position,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['kanban-cards', boardId] });
    },
    onError: async () => {
      messageApi.error('Не удалось переместить карточку');
      await queryClient.invalidateQueries({ queryKey: ['kanban-cards', boardId] });
    },
  });

  const updateCard = useMutation({
    mutationFn: async (values: CardDetailsFormValues) => {
      if (!selectedCard) {
        return;
      }
      await apiClient.put(`/v1/kanban/cards/${selectedCard.id}`, {
        title: values.title,
        description: values.description,
        priority: values.priority,
        assignee_id: values.assignee_id || null,
        deadline: values.deadline ? values.deadline.toISOString() : null,
        tags: values.tags ?? [],
      });
    },
    onSuccess: async () => {
      await refreshBoard();
      messageApi.success('Карточка обновлена');
    },
    onError: () => messageApi.error('Не удалось обновить карточку'),
  });

  const addComment = useMutation({
    mutationFn: async () => {
      if (!selectedCard) {
        return;
      }
      await apiClient.post(`/v1/kanban/cards/${selectedCard.id}/comments`, {
        body: commentBody,
      });
    },
    onSuccess: async () => {
      setCommentBody('');
      if (selectedCard) {
        await queryClient.invalidateQueries({ queryKey: ['kanban-comments', selectedCard.id] });
      }
    },
  });

  const saveCustomFields = useMutation({
    mutationFn: async () => {
      if (!selectedCard || !Object.keys(customFieldDrafts).length) {
        return;
      }
      await apiClient.put(`/v1/kanban/cards/${selectedCard.id}/custom-fields`, customFieldDrafts);
    },
    onSuccess: () => {
      messageApi.success('Кастомные поля обновлены');
    },
    onError: () => {
      messageApi.error('Не удалось обновить кастомные поля');
    },
  });

  const deleteAttachment = useMutation({
    mutationFn: async (documentId: string) => {
      if (!selectedCard) {
        return;
      }
      await apiClient.delete(`/v1/kanban/cards/${selectedCard.id}/attachments/${documentId}`);
    },
    onSuccess: async () => {
      if (selectedCard) {
        await queryClient.invalidateQueries({ queryKey: ['kanban-attachments', selectedCard.id] });
      }
    },
  });

  if (!boardId) {
    return <Alert type="warning" showIcon message="Не найден идентификатор доски" />;
  }

  if (boardQuery.isLoading || cardsQuery.isLoading) {
    return <Spin size="large" />;
  }

  if (boardQuery.isError || !boardQuery.data) {
    return (
      <Space direction="vertical" size={16}>
        <Alert type="error" showIcon message="Не удалось открыть доску" />
        <Button onClick={() => navigate('/kanban')}>Вернуться к списку</Button>
      </Space>
    );
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const activeCard = event.active.data.current as CardItem | undefined;
    const overColumnId = String(event.over?.id ?? '').replace('column:', '');

    if (!activeCard || !overColumnId || activeCard.column_id === overColumnId) {
      return;
    }

    setCardsState((current) => {
      const next: CardsByColumn = {};
      for (const [columnId, cards] of Object.entries(current)) {
        next[columnId] = cards.filter((card) => card.id !== activeCard.id);
      }
      const targetCards = [...(next[overColumnId] ?? [])];
      targetCards.push({ ...activeCard, column_id: overColumnId });
      next[overColumnId] = targetCards;
      return next;
    });

    moveCard.mutate({
      cardId: activeCard.id,
      column_id: overColumnId,
      position: cardsState[overColumnId]?.length ?? 0,
    });
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {contextHolder}
      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
          <Space direction="vertical" size={4}>
            <Typography.Title level={3} style={{ margin: 0 }}>
              {boardQuery.data.name}
            </Typography.Title>
            <Typography.Text type="secondary">
              {boardQuery.data.description || 'Описание не задано'}
            </Typography.Text>
          </Space>
          <Button icon={<PlusOutlined />} onClick={() => setIsColumnModalOpen(true)}>
            Колонка
          </Button>
        </Space>
      </Card>

      <DndContext collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
        <div style={{ display: 'flex', gap: 16, overflowX: 'auto', paddingBottom: 8 }}>
          {boardQuery.data.columns
            .slice()
            .sort((left, right) => left.position - right.position)
            .map((column) => (
              <DroppableColumn
                key={column.id}
                column={column}
                cards={(cardsState[column.id] ?? []).slice().sort((a, b) => a.position - b.position)}
                onOpenCard={setSelectedCard}
                onCreateCard={setCreateCardColumnId}
              />
            ))}
        </div>
      </DndContext>

      <Modal
        title="Новая колонка"
        open={isColumnModalOpen}
        onCancel={() => {
          setIsColumnModalOpen(false);
          columnForm.resetFields();
        }}
        onOk={() => columnForm.submit()}
        confirmLoading={createColumn.isPending}
      >
        <Form form={columnForm} layout="vertical" onFinish={(values) => createColumn.mutate(values)}>
          <Form.Item
            label="Название"
            name="name"
            rules={[{ required: true, message: 'Введите название колонки' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="Цвет" name="color">
            <Input placeholder="#1890ff" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Новая карточка"
        open={Boolean(createCardColumnId)}
        onCancel={() => {
          setCreateCardColumnId(null);
          cardForm.resetFields();
        }}
        onOk={() => cardForm.submit()}
        confirmLoading={createCard.isPending}
      >
        <Form form={cardForm} layout="vertical" onFinish={(values) => createCard.mutate(values)}>
          <Form.Item
            label="Название"
            name="title"
            rules={[{ required: true, message: 'Введите название карточки' }]}
          >
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        width={520}
        title={watchedTitle || selectedCard?.title || 'Карточка'}
        open={Boolean(selectedCard)}
        onClose={() => setSelectedCard(null)}
      >
        {selectedCard ? (
          <Space direction="vertical" size={20} style={{ width: '100%' }}>
            <Typography.Title
              level={4}
              style={{ margin: 0 }}
              editable={{
                onChange: (value) => {
                  detailsForm.setFieldValue('title', value);
                  void updateCard.mutate({
                    ...detailsForm.getFieldsValue(),
                    title: value,
                  });
                },
              }}
            >
              {watchedTitle || selectedCard.title}
            </Typography.Title>
            <Form
              form={detailsForm}
              layout="vertical"
              onFinish={(values) => updateCard.mutate(values)}
            >
              <Form.Item name="title" hidden>
                <Input />
              </Form.Item>
              <Form.Item label="Описание" name="description">
                <Input.TextArea rows={4} />
              </Form.Item>
              <Form.Item label="Приоритет" name="priority">
                <Select
                  options={[
                    { value: 'low', label: 'low' },
                    { value: 'medium', label: 'medium' },
                    { value: 'high', label: 'high' },
                    { value: 'urgent', label: 'urgent' },
                  ]}
                />
              </Form.Item>
              <Form.Item label="Исполнитель" name="assignee_id">
                <Select
                  allowClear
                  options={(usersQuery.data ?? []).map((user) => ({
                    value: user.id,
                    label: user.name,
                  }))}
                />
              </Form.Item>
              <Form.Item label="Дедлайн" name="deadline">
                <DatePicker showTime style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="Теги" name="tags">
                <Select mode="tags" tokenSeparators={[',']} />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={updateCard.isPending}>
                Сохранить
              </Button>
            </Form>

            <Card size="small" title="Комментарии" extra={<CommentOutlined />}>
              <List
                size="small"
                dataSource={commentsQuery.data ?? []}
                renderItem={(item) => (
                  <List.Item>
                    <Space direction="vertical" size={0}>
                      <Typography.Text>{item.body}</Typography.Text>
                      <Typography.Text type="secondary">
                        {new Date(item.created_at).toLocaleString('ru-RU')}
                      </Typography.Text>
                    </Space>
                  </List.Item>
                )}
              />
              <Space direction="vertical" style={{ width: '100%', marginTop: 12 }}>
                <Input.TextArea
                  rows={3}
                  value={commentBody}
                  onChange={(event) => setCommentBody(event.target.value)}
                  placeholder="Добавить комментарий"
                />
                <Button
                  type="primary"
                  onClick={() => addComment.mutate()}
                  disabled={!commentBody.trim()}
                >
                  Отправить
                </Button>
              </Space>
            </Card>

            <Card size="small" title="Вложения" extra={<PaperClipOutlined />}>
              <Upload
                beforeUpload={(file) => {
                  void (async () => {
                    const formData = new FormData();
                    formData.append('file', file);
                    await apiClient.post(`/v1/kanban/cards/${selectedCard.id}/attachments`, formData, {
                      headers: { 'Content-Type': 'multipart/form-data' },
                    });
                    await queryClient.invalidateQueries({
                      queryKey: ['kanban-attachments', selectedCard.id],
                    });
                  })();
                  return false;
                }}
                showUploadList={false}
              >
                <Button>Загрузить файл</Button>
              </Upload>
              <List
                size="small"
                style={{ marginTop: 12 }}
                dataSource={attachmentsQuery.data ?? []}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Button
                        key="download"
                        type="link"
                        onClick={async () => {
                          const response = await apiClient.get<Blob>(
                            `/v1/documents/${item.id}/download`,
                            { responseType: 'blob' },
                          );
                          const url = URL.createObjectURL(response.data);
                          const link = document.createElement('a');
                          link.href = url;
                          link.download = item.original_filename;
                          link.click();
                          URL.revokeObjectURL(url);
                        }}
                      >
                        Скачать
                      </Button>,
                      <Button key="delete" danger type="link" onClick={() => deleteAttachment.mutate(item.id)}>
                        Удалить
                      </Button>,
                    ]}
                  >
                    {item.original_filename}
                  </List.Item>
                )}
              />
            </Card>

            {boardQuery.data.custom_fields.length ? (
              <Card size="small" title="Кастомные поля">
                <Space direction="vertical" style={{ width: '100%' }}>
                  {boardQuery.data.custom_fields.map((field) => (
                    <Input
                      key={field.id}
                      placeholder={field.name}
                      value={customFieldDrafts[field.id] ?? ''}
                      onChange={(event) =>
                        setCustomFieldDrafts((current) => ({
                          ...current,
                          [field.id]: event.target.value,
                        }))
                      }
                    />
                  ))}
                  <Button onClick={() => saveCustomFields.mutate()} loading={saveCustomFields.isPending}>
                    Сохранить поля
                  </Button>
                </Space>
              </Card>
            ) : null}

            <Card size="small" title="История">
              <List
                size="small"
                dataSource={historyQuery.data ?? []}
                renderItem={(item) => (
                  <List.Item>
                    <Space direction="vertical" size={0}>
                      <Typography.Text>
                        {item.from_column_id || 'start'} → {item.to_column_id}
                      </Typography.Text>
                      <Typography.Text type="secondary">
                        {new Date(item.changed_at).toLocaleString('ru-RU')}
                      </Typography.Text>
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}
