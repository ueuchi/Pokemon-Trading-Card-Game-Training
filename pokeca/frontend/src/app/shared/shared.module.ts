import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AutoInputComponent } from './auto-input/auto-input.component';

@NgModule({
  imports: [CommonModule, FormsModule, AutoInputComponent],
  exports: [AutoInputComponent],
})
export class SharedModule {}
