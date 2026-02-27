'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { OrgListData, OrgSummary, OrgMemberListData, OrgEventListData } from '@/lib/types';
import {
  getUserOrgs,
  getOrgBySlug,
  createOrg,
  getOrgMembers,
  addOrgMember,
  removeOrgMember,
  getOrgEvents,
  createOrgEvent,
  deleteOrgEvent,
} from '@/lib/api';

export function useUserOrgs(enabled = true) {
  return useQuery<OrgListData>({
    queryKey: ['orgs'],
    queryFn: getUserOrgs,
    enabled,
    staleTime: 30_000,
  });
}

export function useOrg(slug: string | undefined) {
  return useQuery<OrgSummary>({
    queryKey: ['orgs', slug],
    queryFn: () => getOrgBySlug(slug!),
    enabled: !!slug,
    staleTime: 30_000,
  });
}

export function useOrgMembers(slug: string | undefined) {
  return useQuery<OrgMemberListData>({
    queryKey: ['orgs', slug, 'members'],
    queryFn: () => getOrgMembers(slug!),
    enabled: !!slug,
    staleTime: 30_000,
  });
}

export function useOrgEvents(slug: string | undefined) {
  return useQuery<OrgEventListData>({
    queryKey: ['orgs', slug, 'events'],
    queryFn: () => getOrgEvents(slug!),
    enabled: !!slug,
    staleTime: 30_000,
  });
}

export function useCreateOrg() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      name: string;
      slug: string;
      logoUrl?: string;
      brandColor?: string;
    }) => createOrg(params.name, params.slug, params.logoUrl, params.brandColor),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['orgs'] });
    },
  });
}

export function useAddMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      slug: string;
      userId: string;
      role: string;
      runGroup?: string;
    }) => addOrgMember(params.slug, params.userId, params.role, params.runGroup),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['orgs'] });
    },
  });
}

export function useRemoveMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { slug: string; userId: string }) =>
      removeOrgMember(params.slug, params.userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['orgs'] });
    },
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      slug: string;
      name: string;
      trackName: string;
      eventDate: string;
      runGroups?: string[];
    }) =>
      createOrgEvent(
        params.slug,
        params.name,
        params.trackName,
        params.eventDate,
        params.runGroups,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['orgs'] });
    },
  });
}

export function useDeleteEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { slug: string; eventId: string }) =>
      deleteOrgEvent(params.slug, params.eventId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['orgs'] });
    },
  });
}
