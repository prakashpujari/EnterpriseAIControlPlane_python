/**
 * Documents Page Component
 * Document management and upload interface with drag & drop, multiple file upload,
 * progress tracking, and Pinecone ingestion via RAG pipeline.
 */

import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Button,
  Container,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  CircularProgress,
  Chip,
  Alert,
  AlertTitle,
} from '@mui/material';
import { Upload, Delete, Eye, Info } from 'lucide-react';
import { useAuth } from '../store/authStore';
import axios from 'axios';

interface Document {
  id: string;
  title: string;
  uploaded_at: string;
  status: 'processed' | 'processing' | 'failed';
}

interface UploadItem {
  file: File;
  progress: number; // 0-100
  status: 'idle' | 'uploading' | 'success' | 'error';
  error?: string;
}

export function Documents() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<string | null>(null);
  const [fetchLoading, setFetchLoading] = useState(true);
  const [uploadQueue, setUploadQueue] = useState<UploadItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { user, token } = useAuth();

  const API_BASE_URL = import.meta.env.VITE_API_URL || '';

  // Fetch documents list
  const fetchDocuments = async () => {
    setFetchLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/documents`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      // Assuming response format: { documents: [...] }
      setDocuments(response.data.documents || response.data || []);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
      // Keep empty array
    } finally {
      setFetchLoading(false);
    }
  };

  // Process a single file
  const processFile = async (file: File) => {
    // Update status to uploading
    setUploadQueue(prev => {
      const idx = prev.findIndex(item => item.file === file);
      if (idx >= 0) {
        const newQueue = [...prev];
        newQueue[idx] = { ...newQueue[idx], status: 'uploading', progress: 0 };
        return newQueue;
      }
      return prev;
    });

    const formData = new FormData();
    formData.append('file', file);
    const title = file.name; // use filename as title

    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/documents/upload`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
        // Optional: enable progress tracking if we want to use axios progress events
        // onUploadProgress: (progressEvent) => {
        //   const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        //   setUploadQueue(prev => {
        //     const idx = prev.findIndex(item => item.file === file);
        //     if (idx >= 0) {
        //       const newQueue = [...prev];
        //       newQueue[idx] = { ...newQueue[idx], progress: percent };
        //       return newQueue;
        //     }
        //     return prev;
        //   });
        // },
      });

      console.log('Upload successful:', response.data);
      // Refresh document list after each successful upload
      await fetchDocuments();

      // Mark as success
      setUploadQueue(prev => {
        const idx = prev.findIndex(item => item.file === file);
        if (idx >= 0) {
          const newQueue = [...prev];
          newQueue[idx] = { ...newQueue[idx], status: 'success', progress: 100 };
          return newQueue;
        }
        return prev;
      });
    } catch (error) {
      console.error('Upload failed:', error);
      const errMsg = error.response?.data?.detail || error.message || 'Unknown error';
      // Mark as error
      setUploadQueue(prev => {
        const idx = prev.findIndex(item => item.file === file);
        if (idx >= 0) {
          const newQueue = [...prev];
          newQueue[idx] = { ...newQueue[idx], status: 'error', progress: 0, error: errMsg };
          return newQueue;
        }
        return prev;
      });
    }
  };

  // Handle files from input or drag/drop
  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const filesArray = Array.from(files);
    // Validate file types
    const allowedTypes = [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
    ];
    const invalid = filesArray.find(f => !allowedTypes.includes(f.type));
    if (invalid) {
      alert('Unsupported file type. Please upload PDF, DOC, DOCX, or TXT.');
      return;
    }
    // Initialize queue items
    const initQueue = filesArray.map(f => ({
      file: f,
      progress: 0,
      status: 'idle',
    }));
    setUploadQueue(initQueue);
    // Process each file sequentially
    filesArray.reduce((promise, file) => {
      return promise.then(() => processFile(file));
    }, Promise.resolve());
  };

  // Drag & drop handlers
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };
  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const files = e.dataTransfer.files;
    if (files.length) {
      handleFiles(files);
    }
  };

  // File input change handler
  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    // Reset input to allow same file re-selection if needed
    e.target.value = '';
  };

  const handleDelete = (id: string) => {
    setDocumentToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (documentToDelete && token) {
      try {
        await axios.delete(`${API_BASE_URL}/api/v1/documents/${documentToDelete}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        setDocuments(documents.filter((d) => d.id !== documentToDelete));
        // Reset upload queue in case any were pending
        setUploadQueue([]);
      } catch (error) {
        console.error('Delete failed:', error);
        alert('Delete failed: ' + (error.response?.data?.detail || error.message));
      }
    }
    setDeleteDialogOpen(false);
    setDocumentToDelete(null);
  };

  // Fetch documents on mount and when token changes
  useEffect(() => {
    if (token) {
      fetchDocuments();
    }
  }, [token]);

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column' }}>
          <Typography variant="h4" component="h1">
            Documents
          </Typography>
          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Upload PDF, DOC, DOCX, or TXT files to enable document-based conversations in the chat
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          {/* Hidden file input for programmatic opening */}
          <input
            type="file"
            accept=".pdf,.doc,.docx,.txt"
            multiple
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={onFileChange}
          />
          <Button
            variant="contained"
            startIcon={<Upload />}
            disabled={uploadQueue.some(item => item.status === 'uploading') || !token}
            onClick={() => fileInputRef.current?.click()}
          >
            Upload Document
          </Button>
          {/* Show overall progress if any uploads in progress */}
          {uploadQueue.some(item => item.status === 'uploading') && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.primary">
                Uploading...
              </Typography>
              <LinearProgress size={3} sx={{ width: 200 }} />
            </Box>
          )}
        </Box>
      </Box>

      {/* Sample/Help Section */}
      <Paper elevation={3} sx={{ mb: 4 }}>
        <Box sx={{ p: 3 }}>
          <Typography variant="h6" component="h2" gutterBottom>
            How to Use
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Upload PDF, DOC, DOCX, or TXT files to store them in the vector database for retrieval-augmented generation (RAG).
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2 }}>
            <Box sx={{ border: '1px solid', borderRadius: 2, p: 2 }}>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <Info fontSize={18} color="info.main" />
              </Typography>
              <Typography variant="body2" fontWeight="medium">
                Supported Formats
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                PDF, DOC, DOCX, TXT
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Maximum size: 10MB
              </Typography>
            </Box>

            <Box sx={{ border: '1px solid', borderRadius: 2, p: 2 }}>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <Info fontSize={18} color="info.main" />
              </Typography>
              <Typography variant="body2" fontWeight="medium">
                How It Works
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                Upload → Text Extraction → Vector Storage → RAG Ready
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Files are processed and made available for chat queries
              </Typography>
            </Box>
          </Box>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Tip: Once uploaded, you can ask questions about your documents in the chat interface!
            </Typography>
          </Box>
        </Box>
      </Paper>

      <Paper elevation={3}>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Uploaded</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {fetchLoading ? (
                <TableRow>
                  <TableCell colSpan={4} sx={{ textAlign: 'center', py: 4 }}>
                    <LinearProgress size={3} />
                    Loading documents...
                  </TableCell>
                </TableRow>
              ) : documents.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} sx={{ textAlign: 'center', py: 4 }}>
                    No documents uploaded yet.
                  </TableCell>
                </TableRow>
              ) : (
                documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell>{doc.title}</TableCell>
                    <TableCell>
                      <Box sx={{
                        px: 1,
                        py: 0.5,
                        borderRadius: 1,
                        bgcolor: doc.status === 'processed' ? 'success.light' :
                                 doc.status === 'processing' ? 'warning.light' : 'error.light',
                        color: 'text.primary',
                        fontSize: '0.75rem'
                      }}>
                        {doc.status}
                      </Box>
                    </TableCell>
                    <TableCell>{doc.uploaded_at}</TableCell>
                    <TableCell align="right">
                      <IconButton size="small">
                        <Eye />
                      </IconButton>
                      <IconButton size="small" onClick={() => handleDelete(doc.id)}>
                        <Delete />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Upload Queue Section */}
      {uploadQueue.length > 0 && (
        <Paper elevation={3} sx={{ mt: 4, p: 3 }}>
          <Typography variant="h6" component="h3" gutterBottom>
            Upload Queue
          </Typography>
          <Box sx={{ mb: 2 }}>
            {uploadQueue.map((item, index) => (
              <Box key={index} sx={{ mb: 2 }}>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  {item.file.name} –{' '}
                  {item.status === 'idle' && 'Waiting'}
                  {item.status === 'uploading' && 'Uploading...'}
                  {item.status === 'success' && 'Success'}
                  {item.status === 'error' && `Error: ${item.error}`}
                </Typography>
                {item.status === 'uploading' && (
                  <LinearProgress size={2} value={item.progress} sx={{ width: '100%' }} />
                )}
                {item.status === 'error' && (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    <AlertTitle>Error</AlertTitle>
                    {item.error}
                  </Alert>
                )}
              </Box>
            ))}
          </Box>
        </Paper>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>Delete Document</DialogTitle>
        <DialogContent>
          Are you sure you want to delete this document? This action cannot be undone.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmDelete} color="error" autoFocus>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}