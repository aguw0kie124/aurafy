import { createContext, useContext } from 'react';
import { emptyMusicData, type MusicData } from '@/lib/data/music';

// App owns the loaded stats and hands them down; pages read them with useMusicData().
export const MusicDataContext = createContext<MusicData>(emptyMusicData());

export function useMusicData() {
	return useContext(MusicDataContext);
}
