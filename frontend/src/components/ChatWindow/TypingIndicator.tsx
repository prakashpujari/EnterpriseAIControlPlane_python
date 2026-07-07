/**
 * TypingIndicator Component
 * Shows animated typing indicator for assistant responses
 */

import { Box, Avatar, Stack } from '@mui/material';
import { Bot } from 'lucide-react';
import { motion } from 'framer-motion';

export function TypingIndicator() {
  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 2 }}>
      <Avatar
        sx={{
          width: 32,
          height: 32,
          bgcolor: 'secondary.main',
        }}
      >
        <Bot size={18} />
      </Avatar>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          p: 1.5,
          borderRadius: 2,
          backgroundColor: 'background.paper',
          border: 1,
          borderColor: 'divider',
          ml: 1,
        }}
      >
        <Box sx={{ display: 'flex', gap: 2 }}>
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              animate={{
                scale: [1, 1.2, 1],
                opacity: [0.4, 1, 0.4],
              }}
              transition={{
                duration: 0.8,
                repeat: Infinity,
                delay: i * 0.1,
              }}
            >
              <Box
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  bgcolor: 'text.primary',
                }}
              />
            </motion.div>
          ))}
        </Box>
        <Box sx={{ ml: 1 }}>
          <Box component="span" sx={{ fontSize: 12, color: 'text.secondary' }}>
            Assistant is thinking...
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
