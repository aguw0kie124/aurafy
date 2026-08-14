import { useEffect, useState } from 'react';
import { X, ExternalLink } from 'lucide-react';
import MediaThumb from '@/lib/components/MediaThumb';
import { createPlaylist, type ProposedTrack } from '@/lib/data/music';
import styles from './PlaylistModal.module.css';

type ModalPlaylist = {
	name: string;
	description: string;
	tracks: ProposedTrack[];
	trackUris: string[];
};

const skeletonRows = Array.from({ length: 8 }, (_, i) => i);

export default function PlaylistModal({
	open = false,
	loading = false,
	playlist = null,
	onClose
}: {
	open?: boolean;
	loading?: boolean;
	playlist?: ModalPlaylist | null;
	onClose: () => void;
}) {
	const [saving, setSaving] = useState(false);
	const [savedUrl, setSavedUrl] = useState<string | null>(null);
	const [errorMessage, setErrorMessage] = useState('');

	const playlistId = playlist ? `${playlist.name}:${playlist.trackUris.length}` : '';

	// Reset the save state whenever a new playlist is shown.
	useEffect(() => {
		setSavedUrl(null);
		setErrorMessage('');
		setSaving(false);
	}, [playlistId]);

	useEffect(() => {
		if (!open) return;

		const handleKeydown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') onClose();
		};

		window.addEventListener('keydown', handleKeydown);
		return () => window.removeEventListener('keydown', handleKeydown);
	}, [open, onClose]);

	async function save() {
		if (!playlist) return;
		setSaving(true);
		setErrorMessage('');
		try {
			const result = await createPlaylist({
				name: playlist.name,
				description: playlist.description,
				trackUris: playlist.trackUris,
				isPublic: false
			});
			setSavedUrl(result.spotifyUrl);
		} catch (error) {
			setErrorMessage(error instanceof Error ? error.message : 'Could not save to Spotify.');
		} finally {
			setSaving(false);
		}
	}

	function onBackdrop(event: React.MouseEvent) {
		if (event.target === event.currentTarget) onClose();
	}

	if (!open) return null;

	return (
		<div className={styles.overlay} onClick={onBackdrop} role="presentation">
			<div className={styles.modal} role="dialog" aria-modal="true" aria-label="Playlist">
				<button className={styles.close} type="button" aria-label="Close" onClick={onClose}>
					<X size={20} strokeWidth={2.2} />
				</button>

				{loading ? (
					<>
						<header className={styles.modalHead}>
							<div>
								<h2>Building your playlist…</h2>
								<p>Finding tracks that match your vibe.</p>
							</div>
						</header>
						<ol className={styles.tracklist} aria-hidden="true">
							{skeletonRows.map((row) => (
								<li key={row} className={`${styles.track} ${styles.skeletonRow}`}>
									<span className={`skeleton ${styles.skelThumb}`}></span>
									<span className={styles.skelCopy}>
										<span className={`skeleton ${styles.skelLine}`} style={{ width: '60%' }}></span>
										<span className={`skeleton ${styles.skelLine}`} style={{ width: '40%' }}></span>
									</span>
								</li>
							))}
						</ol>
					</>
				) : playlist ? (
					<>
						<header className={styles.modalHead}>
							<div>
								<h2>{playlist.name}</h2>
								{playlist.description && <p>{playlist.description}</p>}
								<small>{playlist.tracks.length} tracks</small>
							</div>
							<div className={styles.actions}>
								{savedUrl ? (
									<a
										className={styles.primary}
										href={savedUrl}
										target="_blank"
										rel="noreferrer noopener"
									>
										<ExternalLink size={16} strokeWidth={2.2} /> Open in Spotify
									</a>
								) : (
									<button type="button" className={styles.primary} onClick={save} disabled={saving}>
										{saving ? 'Saving…' : 'Save to Spotify'}
									</button>
								)}
							</div>
						</header>

						{errorMessage && <p className={styles.error}>{errorMessage}</p>}

						<ol className={styles.tracklist}>
							{playlist.tracks.map((track, index) => (
								<li key={track.spotifyTrackId ?? index} className={styles.track}>
									<span className={styles.num}>{index + 1}</span>
									<MediaThumb
										kind="cover"
										src={track.coverUrl}
										alt={`${track.album} artwork`}
										size="small"
										label={track.title}
									/>
									<span className={styles.trackCopy}>
										<strong>{track.title}</strong>
										<small>{track.artist}</small>
									</span>
									{track.externalUrl && (
										<a
											className={styles.open}
											href={track.externalUrl}
											target="_blank"
											rel="noreferrer noopener"
											aria-label={`Open ${track.title} in Spotify`}
										>
											<ExternalLink size={16} strokeWidth={2.2} />
										</a>
									)}
								</li>
							))}
						</ol>
					</>
				) : null}
			</div>
		</div>
	);
}
