import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Space,
  Typography,
  message,
} from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiClient } from '../api/client';

type BoardItem = {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  card_count: number;
  created_at: string;
  updated_at: string;
};

type BoardFormValues = {
  name: string;
  description?: string;
};

async function fetchBoards(): Promise<BoardItem[]> {
  const { data } = await apiClient.get<BoardItem[]>('/v1/kanban/boards');
  return data;
}

export function KanbanBoardsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm<BoardFormValues>();

  const boardsQuery = useQuery({
    queryKey: ['kanban-boards'],
    queryFn: fetchBoards,
  });

  const createBoard = useMutation({
    mutationFn: async (values: BoardFormValues) => {
      const { data } = await apiClient.post<BoardItem>('/v1/kanban/boards', values);
      return data;
    },
    onSuccess: async (board) => {
      await queryClient.invalidateQueries({ queryKey: ['kanban-boards'] });
      form.resetFields();
      setIsModalOpen(false);
      messageApi.success('Доска создана');
      navigate(`/kanban/${board.id}`);
    },
    onError: () => {
      messageApi.error('Не удалось создать доску');
    },
  });

  const deleteBoard = useMutation({
    mutationFn: async (boardId: string) => {
      await apiClient.delete(`/v1/kanban/boards/${boardId}`);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['kanban-boards'] });
      messageApi.success('Доска удалена');
    },
    onError: () => {
      messageApi.error('Не удалось удалить доску');
    },
  });

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {contextHolder}
      <Card>
        <Space direction="vertical" size={4}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            Канбан-доски
          </Typography.Title>
          <Typography.Text type="secondary">
            Рабочие доски Sprint 1 для задач, дедлайнов и вложений.
          </Typography.Text>
        </Space>
      </Card>

      <Card>
        <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Доступные доски
          </Typography.Title>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)}>
            Создать доску
          </Button>
        </Space>
      </Card>

      {boardsQuery.isError ? (
        <Alert type="warning" showIcon message="Не удалось загрузить доски" />
      ) : null}

      {boardsQuery.data?.length ? (
        <Row gutter={[16, 16]}>
          {boardsQuery.data.map((board) => (
            <Col key={board.id} xs={24} md={12} xl={8}>
              <Card
                hoverable
                onClick={() => navigate(`/kanban/${board.id}`)}
                actions={[
                  <Popconfirm
                    key="delete"
                    title="Удалить доску?"
                    okText="Удалить"
                    cancelText="Отмена"
                    onConfirm={(event) => {
                      event?.stopPropagation();
                      deleteBoard.mutate(board.id);
                    }}
                  >
                    <Button
                      danger
                      type="text"
                      icon={<DeleteOutlined />}
                      onClick={(event) => event.stopPropagation()}
                    >
                      Удалить
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Typography.Title level={4} style={{ margin: 0 }}>
                    {board.name}
                  </Typography.Title>
                  <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    {board.description || 'Описание не задано'}
                  </Typography.Paragraph>
                  <Typography.Text type="secondary">
                    Карточек: {board.card_count}
                  </Typography.Text>
                  <Typography.Text type="secondary">
                    Обновлена: {new Date(board.updated_at).toLocaleString('ru-RU')}
                  </Typography.Text>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <Card loading={boardsQuery.isLoading}>
          <Empty description="Пока нет ни одной доски" />
        </Card>
      )}

      <Modal
        title="Создать доску"
        open={isModalOpen}
        onCancel={() => {
          setIsModalOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={createBoard.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(values) => createBoard.mutate(values)}>
          <Form.Item
            label="Название"
            name="name"
            rules={[{ required: true, message: 'Введите название доски' }]}
          >
            <Input placeholder="Sprint 1" />
          </Form.Item>
          <Form.Item label="Описание" name="description">
            <Input.TextArea rows={4} placeholder="Короткое описание доски" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
