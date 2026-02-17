import { Component } from '@angular/core';
// import { RouterOutlet, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MaterialModule } from './shared/material.module';
import { GameBoardComponent } from './components/game-board/game-board.component';
import { CardCreatorComponent } from './components/card-creator/card-creator.component';
import { DeckBuilderComponent } from './components/deck-builder/deck-builder.component';
import { CardViewerComponent } from './components/card-viewer/card-viewer.component';

@Component({
  selector: 'app-root',
  standalone: true,
  // imports: [RouterOutlet, RouterLink, CommonModule],
  imports: [
    CommonModule,
    MaterialModule,
    GameBoardComponent,
    CardCreatorComponent,
    DeckBuilderComponent,
    CardViewerComponent,
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent {
  currentView: 'game' | 'creator' | 'deck' | 'cards' = 'cards';
  title = 'card-game-engine';
}

// import { Component } from '@angular/core';
// import { GameBoardComponent } from './components/game-board/game-board.component';

// @Component({
//   selector: 'app-root',
//   standalone: true,
//   imports: [GameBoardComponent],
//   templateUrl: './app.component.html',
//   styleUrl: './app.component.scss',
// })
// export class AppComponent {
//   title = 'card-game-engine';
// }
