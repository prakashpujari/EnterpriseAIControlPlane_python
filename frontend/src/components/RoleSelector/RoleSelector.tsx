/**
 * RoleSelector Component
 * Allows users to select their role for context filtering
 */

import { useState } from 'react';
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  Card,
  CardContent,
  Avatar,
  Chip,
  Stack,
} from '@mui/material';
import {
  Shield,
  Calculator,
  FileText,
  LayoutDashboard,
} from 'lucide-react';

export type UserRole =
  | 'support_engineer'
  | 'mortgage_analyst'
  | 'compliance_officer'
  | 'product_owner';

interface Role {
  id: UserRole;
  name: string;
  description: string;
  icon: React.ElementType;
  color: string;
}

const ROLES: Role[] = [
  {
    id: 'support_engineer',
    name: 'Support Engineer',
    description: 'Customer support and troubleshooting',
    icon: Shield,
    color: 'primary.main',
  },
  {
    id: 'mortgage_analyst',
    name: 'Mortgage Analyst',
    description: 'Loan analysis and underwriting',
    icon: Calculator,
    color: 'secondary.main',
  },
  {
    id: 'compliance_officer',
    name: 'Compliance Officer',
    description: 'Regulatory compliance and audits',
    icon: FileText,
    color: 'success.main',
  },
  {
    id: 'product_owner',
    name: 'Product Owner',
    description: 'Product strategy and requirements',
    icon: LayoutDashboard,
    color: 'warning.main',
  },
];

interface RoleSelectorProps {
  selectedRole: UserRole;
  onRoleChange: (role: UserRole) => void;
}

export function RoleSelector({ selectedRole, onRoleChange }: RoleSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleChange = (event: SelectChangeEvent) => {
    const newRole = event.target.value as UserRole;
    onRoleChange(newRole);
  };

  const selectedRoleData = ROLES.find((r) => r.id === selectedRole);
  const SelectedIcon = selectedRoleData?.icon || Shield;

  return (
    <Card
      variant="outlined"
      sx={{
        mb: 2,
        cursor: 'pointer',
        '&:hover': {
          borderColor: 'primary.main',
          boxShadow: 1,
        },
      }}
      onClick={() => setIsOpen(true)}
    >
      <CardContent>
        <Stack direction="row" alignItems="center" spacing={2}>
          <Avatar
            sx={{
              width: 40,
              height: 40,
              bgcolor: selectedRoleData?.color || 'primary.main',
            }}
          >
            <SelectedIcon />
          </Avatar>

          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Your Role
            </Typography>
            <Typography variant="h6">
              {selectedRoleData?.name || 'Select Role'}
            </Typography>
          </Box>

          <Chip
            label={selectedRole?.replace('_', ' ').toUpperCase()}
            size="small"
            variant="outlined"
            color="primary"
          />
        </Stack>
      </CardContent>
    </Card>
  );
}

/**
 * RoleDropdown Component for inline selection
 */
export function RoleDropdown({
  selectedRole,
  onRoleChange,
}: {
  selectedRole: UserRole;
  onRoleChange: (role: UserRole) => void;
}) {
  return (
    <FormControl fullWidth size="small">
      <InputLabel>Role</InputLabel>
      <Select
        value={selectedRole}
        label="Role"
        onChange={(e) => onRoleChange(e.target.value as UserRole)}
      >
        {ROLES.map((role) => {
          const RoleIcon = role.icon;
          return (
            <MenuItem key={role.id} value={role.id}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <RoleIcon size={18} />
                <span>{role.name}</span>
              </Box>
            </MenuItem>
          );
        })}
      </Select>
    </FormControl>
  );
}
