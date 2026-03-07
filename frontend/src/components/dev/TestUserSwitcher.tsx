'use client';

import { useEffect, useState } from 'react';

const TEST_USERS = [
  { id: 'dev-user', label: 'Dev User (default)', color: '#6b7280' },
  { id: 'test-alex', label: 'Alex Racer', color: '#3b82f6' },
  { id: 'test-jordan', label: 'Jordan Swift', color: '#22c55e' },
  { id: 'test-morgan', label: 'Morgan Apex', color: '#f59e0b' },
] as const;

/**
 * Floating dev-tools panel for switching between test users.
 * Only rendered when NEXT_PUBLIC_TEST_AUTH=true.
 * Sets localStorage.testUserId which is picked up by fetchApi().
 */
export function TestUserSwitcher() {
  const [currentUser, setCurrentUser] = useState('dev-user');
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem('testUserId');
    if (stored) setCurrentUser(stored);
  }, []);

  const handleSelect = (userId: string) => {
    if (userId === 'dev-user') {
      localStorage.removeItem('testUserId');
    } else {
      localStorage.setItem('testUserId', userId);
    }
    setCurrentUser(userId);
    setExpanded(false);
    window.location.reload();
  };

  const active = TEST_USERS.find((u) => u.id === currentUser) ?? TEST_USERS[0];

  return (
    <div className="fixed bottom-4 right-4 z-[9999]">
      {expanded && (
        <div className="mb-2 rounded-lg border border-yellow-600/40 bg-gray-900/95 p-2 shadow-xl backdrop-blur-sm">
          <p className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider text-yellow-500">
            Switch Test User
          </p>
          {TEST_USERS.map((user) => (
            <button
              key={user.id}
              onClick={() => handleSelect(user.id)}
              className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors ${
                currentUser === user.id
                  ? 'bg-white/10 text-white'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: user.color }}
              />
              {user.label}
            </button>
          ))}
        </div>
      )}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 rounded-full border border-yellow-600/40 bg-gray-900/90 px-3 py-1.5 text-xs font-medium text-yellow-400 shadow-lg backdrop-blur-sm transition-colors hover:bg-gray-800"
        title="Test User Switcher"
      >
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ backgroundColor: active.color }}
        />
        {active.label}
      </button>
    </div>
  );
}
