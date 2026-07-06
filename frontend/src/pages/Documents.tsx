/**
 * Documents Page Component
 * Document management and upload interface
 */

import { useState } from 'react';
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
} from '@mui/material';
import { Upload, Delete, Eye } from 'lucide-react';
import { useAuth } from '../store/authStore';

interface Document {
  id: string;
  title: string;
  uploaded_at: string;
  status: 'processed' | 'processing' | 'failed';
}

export function Documents() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<string | null>(null);
  const { user } = useAuth();

  const handleUpload = () => {
    // TODO: Implement document upload
    console.log('Upload clicked');
  };

  const handleDelete = (id: string) => {
    setDocumentToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (documentToDelete) {
      setDocuments(documents.filter(d => d.id !== documentToDelete));
    }
    setDeleteDialogOpen(false);
    setDocumentToDelete(null);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Documents
        </Typography>
        <Button
          variant="contained"
          startIcon={<Upload />}
          onClick={handleUpload}
        >
          Upload Document
        </Button>
      </Box>

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
              {documents.length === 0 ? (
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
