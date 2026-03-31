import { DeleteOutlined, DownloadOutlined, InboxOutlined, UploadOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadProps } from 'antd';
import dayjs, { type Dayjs } from 'dayjs';
import { useEffect, useState } from 'react';

import { apiClient } from '../api/client';
import { useAuthStore } from '../auth/store';

type DocumentItem = {
  id: string;
  filename: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  category: string;
  entity_type: string;
  entity_id: string | null;
  uploaded_by: string;
  created_at: string;
};

type AuditLogItem = {
  id: string;
  document_id: string;
  document_name: string;
  user_id: string;
  user_name: string;
  action: 'upload' | 'download' | 'delete';
  ip_address: string | null;
  created_at: string;
};

type DocumentFilters = {
  category?: string;
  entity_type?: string;
  q?: string;
};

type AuditFilters = {
  action?: string;
  date_from?: string;
  date_to?: string;
};

type UploadFormValues = {
  category: string;
  entityType: string;
  entityId?: string;
};

const categoryOptions = [
  { value: 'contract', label: 'Договор' },
  { value: 'instruction', label: 'Инструкция' },
  { value: 'invoice', label: 'Накладная' },
  { value: 'photo', label: 'Фото' },
  { value: 'attachment', label: 'Вложение' },
  { value: 'other', label: 'Прочее' },
];

const entityOptions = [
  { value: 'point', label: 'Точка' },
  { value: 'franchisee', label: 'Франчайзи' },
  { value: 'task', label: 'Задача' },
  { value: 'card', label: 'Карточка' },
  { value: 'general', label: 'Общий документ' },
];

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} Б`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} КБ`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} МБ`;
}

function actionColor(action: AuditLogItem['action']): string {
  if (action === 'upload') {
    return 'green';
  }
  if (action === 'download') {
    return 'blue';
  }
  return 'red';
}

async function fetchDocuments(filters: DocumentFilters): Promise<DocumentItem[]> {
  const { data } = await apiClient.get<DocumentItem[]>('/v1/documents', { params: filters });
  return data;
}

async function fetchAuditLog(filters: AuditFilters): Promise<AuditLogItem[]> {
  const { data } = await apiClient.get<AuditLogItem[]>('/v1/documents/audit-log', {
    params: filters,
  });
  return data;
}

export function DocumentsPage() {
  const role = useAuthStore((state) => state.role);
  const queryClient = useQueryClient();
  const [messageApi, contextHolder] = message.useMessage();
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [activeTab, setActiveTab] = useState('documents');
  const [documentFilters, setDocumentFilters] = useState<DocumentFilters>({});
  const [auditFilters, setAuditFilters] = useState<AuditFilters>({});
  const [searchInput, setSearchInput] = useState('');
  const [uploadForm] = Form.useForm<UploadFormValues>();

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDocumentFilters((current) => ({
        ...current,
        q: searchInput.trim() || undefined,
      }));
    }, 300);

    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const documentsQuery = useQuery({
    queryKey: ['documents', documentFilters],
    queryFn: () => fetchDocuments(documentFilters),
  });

  const auditQuery = useQuery({
    queryKey: ['documents-audit', auditFilters],
    queryFn: () => fetchAuditLog(auditFilters),
    enabled: role === 'super_admin' && activeTab === 'audit',
  });

  const deleteMutation = useMutation({
    mutationFn: async (documentId: string) => {
      await apiClient.delete(`/v1/documents/${documentId}`);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
      messageApi.success('Документ удалён');
    },
    onError: () => {
      messageApi.error('Не удалось удалить документ');
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async (values: UploadFormValues) => {
      if (!selectedFile) {
        throw new Error('file-required');
      }

      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('category', values.category);
      formData.append('entity_type', values.entityType);
      if (values.entityId?.trim()) {
        formData.append('entity_id', values.entityId.trim());
      }

      const { data } = await apiClient.post<DocumentItem>('/v1/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (event) => {
          if (event.total) {
            setUploadProgress(Math.round((event.loaded * 100) / event.total));
          }
        },
      });
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
      uploadForm.resetFields();
      setSelectedFile(null);
      setUploadProgress(0);
      setIsUploadOpen(false);
      messageApi.success('Документ загружен');
    },
    onError: () => {
      messageApi.error('Не удалось загрузить документ');
    },
  });

  const documentsColumns: ColumnsType<DocumentItem> = [
    {
      title: 'Имя файла',
      dataIndex: 'original_filename',
      key: 'original_filename',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{record.original_filename}</Typography.Text>
          <Typography.Text type="secondary">
            {record.mime_type} · {formatBytes(record.size_bytes)}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: 'Категория',
      dataIndex: 'category',
      key: 'category',
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: 'Привязка',
      key: 'binding',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Typography.Text>{record.entity_type}</Typography.Text>
          <Typography.Text type="secondary">{record.entity_id ?? 'без ID'}</Typography.Text>
        </Space>
      ),
    },
    {
      title: 'Загрузил',
      dataIndex: 'uploaded_by',
      key: 'uploaded_by',
      render: (value: string) => <Typography.Text code>{value.slice(0, 8)}</Typography.Text>,
    },
    {
      title: 'Дата',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => formatDate(value),
    },
    {
      title: 'Действия',
      key: 'actions',
      render: (_, record) => (
        <Space size="small">
          <Button
            icon={<DownloadOutlined />}
            onClick={async () => {
              try {
                const response = await apiClient.get<Blob>(
                  `/v1/documents/${record.id}/download`,
                  { responseType: 'blob' },
                );
                const url = URL.createObjectURL(response.data);
                const link = document.createElement('a');
                link.href = url;
                link.download = record.original_filename;
                link.click();
                URL.revokeObjectURL(url);
              } catch {
                messageApi.error('Не удалось скачать документ');
              }
            }}
          />
          {role !== 'staff' ? (
            <Popconfirm
              title="Удалить документ?"
              okText="Удалить"
              cancelText="Отмена"
              onConfirm={() => deleteMutation.mutate(record.id)}
            >
              <Button danger icon={<DeleteOutlined />} />
            </Popconfirm>
          ) : null}
        </Space>
      ),
    },
  ];

  const auditColumns: ColumnsType<AuditLogItem> = [
    {
      title: 'Дата',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string) => formatDate(value),
    },
    {
      title: 'Пользователь',
      dataIndex: 'user_name',
      key: 'user_name',
      render: (value: string, record) => value || record.user_id,
    },
    {
      title: 'Действие',
      dataIndex: 'action',
      key: 'action',
      render: (value: AuditLogItem['action']) => <Tag color={actionColor(value)}>{value}</Tag>,
    },
    {
      title: 'Документ',
      dataIndex: 'document_name',
      key: 'document_name',
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      render: (value: string | null) => value ?? '—',
    },
  ];

  const uploadProps: UploadProps = {
    multiple: false,
    maxCount: 1,
    beforeUpload: (file) => {
      setSelectedFile(file);
      return false;
    },
    onRemove: () => {
      setSelectedFile(null);
    },
    fileList: selectedFile ? [selectedFile as never] : [],
  };

  const handleAuditRangeChange = (values: null | [Dayjs | null, Dayjs | null]) => {
    setAuditFilters((current) => ({
      ...current,
      date_from: values?.[0] ? values[0].startOf('day').toISOString() : undefined,
      date_to: values?.[1] ? values[1].endOf('day').toISOString() : undefined,
    }));
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {contextHolder}
      <Card>
        <Space direction="vertical" size={4}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            Документы
          </Typography.Title>
          <Typography.Text type="secondary">
            Приватное хранилище документов с аудитом скачиваний и удалений.
          </Typography.Text>
        </Space>
      </Card>

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'documents',
              label: 'Документы',
              children: (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <Space wrap>
                    <Input.Search
                      allowClear
                      placeholder="Поиск по имени"
                      value={searchInput}
                      onChange={(event) => setSearchInput(event.target.value)}
                      style={{ width: 280 }}
                    />
                    <Select
                      allowClear
                      placeholder="Категория"
                      options={categoryOptions}
                      style={{ width: 180 }}
                      onChange={(value) =>
                        setDocumentFilters((current) => ({ ...current, category: value }))
                      }
                    />
                    <Select
                      allowClear
                      placeholder="Тип привязки"
                      options={entityOptions}
                      style={{ width: 180 }}
                      onChange={(value) =>
                        setDocumentFilters((current) => ({ ...current, entity_type: value }))
                      }
                    />
                    {role !== 'staff' ? (
                      <Button
                        type="primary"
                        icon={<UploadOutlined />}
                        onClick={() => setIsUploadOpen(true)}
                      >
                        Загрузить документ
                      </Button>
                    ) : null}
                  </Space>

                  {documentsQuery.isError ? (
                    <Alert
                      type="warning"
                      showIcon
                      message="Не удалось загрузить список документов"
                    />
                  ) : null}

                  <Table
                    rowKey="id"
                    columns={documentsColumns}
                    dataSource={documentsQuery.data ?? []}
                    loading={documentsQuery.isLoading}
                    pagination={{ pageSize: 10 }}
                  />
                </Space>
              ),
            },
            ...(role === 'super_admin'
              ? [
                  {
                    key: 'audit',
                    label: 'Журнал',
                    children: (
                      <Space direction="vertical" size={16} style={{ width: '100%' }}>
                        <Space wrap>
                          <Select
                            allowClear
                            placeholder="Действие"
                            options={[
                              { value: 'upload', label: 'upload' },
                              { value: 'download', label: 'download' },
                              { value: 'delete', label: 'delete' },
                            ]}
                            style={{ width: 180 }}
                            onChange={(value) =>
                              setAuditFilters((current) => ({ ...current, action: value }))
                            }
                          />
                          <DatePicker.RangePicker onChange={handleAuditRangeChange} />
                        </Space>

                        {auditQuery.isError ? (
                          <Alert
                            type="warning"
                            showIcon
                            message="Не удалось загрузить журнал документов"
                          />
                        ) : null}

                        <Table
                          rowKey="id"
                          columns={auditColumns}
                          dataSource={auditQuery.data ?? []}
                          loading={auditQuery.isLoading}
                          pagination={{ pageSize: 10 }}
                        />
                      </Space>
                    ),
                  },
                ]
              : []),
          ]}
        />
      </Card>

      <Modal
        title="Загрузка документа"
        open={isUploadOpen}
        onCancel={() => {
          setIsUploadOpen(false);
          setSelectedFile(null);
          setUploadProgress(0);
          uploadForm.resetFields();
        }}
        onOk={() => uploadForm.submit()}
        okText="Загрузить"
        confirmLoading={uploadMutation.isPending}
      >
        <Form
          form={uploadForm}
          layout="vertical"
          initialValues={{ category: 'other', entityType: 'general' }}
          onFinish={(values) => uploadMutation.mutate(values)}
        >
          <Form.Item label="Файл" required>
            <Upload.Dragger {...uploadProps}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">Перетащите файл или нажмите для выбора</p>
            </Upload.Dragger>
          </Form.Item>
          <Form.Item
            label="Категория"
            name="category"
            rules={[{ required: true, message: 'Выберите категорию' }]}
          >
            <Select options={categoryOptions} />
          </Form.Item>
          <Form.Item
            label="Тип привязки"
            name="entityType"
            rules={[{ required: true, message: 'Выберите тип привязки' }]}
          >
            <Select options={entityOptions} />
          </Form.Item>
          <Form.Item label="Entity ID" name="entityId">
            <Input placeholder="UUID сущности" />
          </Form.Item>
          {uploadMutation.isPending ? <Progress percent={uploadProgress} /> : null}
        </Form>
      </Modal>
    </Space>
  );
}
