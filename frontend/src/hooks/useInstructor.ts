'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { StudentListData, FlagListData, StudentSessionsData } from '@/lib/types';
import {
  getStudents,
  createInvite,
  acceptInvite,
  removeStudent,
  getStudentSessions,
  getStudentFlags,
  createStudentFlag,
} from '@/lib/api';

export function useStudents(enabled = true) {
  return useQuery<StudentListData>({
    queryKey: ['instructor', 'students'],
    queryFn: getStudents,
    enabled,
    staleTime: 30_000,
  });
}

export function useStudentSessions(studentId: string | undefined) {
  return useQuery<StudentSessionsData>({
    queryKey: ['instructor', 'student-sessions', studentId],
    queryFn: () => getStudentSessions(studentId!),
    enabled: !!studentId,
    staleTime: 30_000,
  });
}

export function useStudentFlags(studentId: string | undefined) {
  return useQuery<FlagListData>({
    queryKey: ['instructor', 'student-flags', studentId],
    queryFn: () => getStudentFlags(studentId!),
    enabled: !!studentId,
    staleTime: 30_000,
  });
}

export function useCreateInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => createInvite(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['instructor'] });
    },
  });
}

export function useAcceptInvite() {
  return useMutation({
    mutationFn: (code: string) => acceptInvite(code),
  });
}

export function useRemoveStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (studentId: string) => removeStudent(studentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['instructor'] });
    },
  });
}

export function useCreateFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      studentId: string;
      flagType: string;
      description: string;
      sessionId?: string;
    }) =>
      createStudentFlag(
        params.studentId,
        params.flagType,
        params.description,
        params.sessionId,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['instructor'] });
    },
  });
}
