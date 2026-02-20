import { Routes } from '@angular/router';
import { GameBoardComponent } from './components/game-board/game-board.component';
import { CardCreatorComponent } from './components/card-creator/card-creator.component';

export const routes: Routes = [
  { path: '', redirectTo: '/game', pathMatch: 'full' },
  { path: 'game', component: GameBoardComponent },
  { path: 'creator', component: CardCreatorComponent },
  { path: '**', redirectTo: '/game' },
];
