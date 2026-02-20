import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MaterialModule } from '../material.module';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { map, startWith } from 'rxjs/operators';
import { Observable } from 'rxjs';

@Component({
  selector: 'auto-input',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, MaterialModule],
  templateUrl: './auto-input.component.html',
  styleUrls: ['./auto-input.component.scss'],
})
export class AutoInputComponent {
  @Input() label = '';
  @Input() placeholder = '';
  /** 選択肢のリスト */
  @Input() options: string[] = [];

  @Output() valueChange = new EventEmitter<string>();

  inputValue = '';
  filteredOptions: string[] = [];
  showList = false;

  /** 名前入力補助 */
  nameCtrl = new FormControl('');

  filteredNames: Observable<string[]> = this.nameCtrl.valueChanges.pipe(
    startWith(''),
    map((value) => this.filter(value || '')),
  );

  onInput() {
    const v = this.normalizeKana(this.inputValue);
    this.filteredOptions = this.options.filter((opt) => this.normalizeKana(opt).includes(v));
    this.showList = this.filteredOptions.length > 0;
  }

  select(value: string) {
    this.inputValue = value;
    this.showList = false;
    this.valueChange.emit(value);
  }

  onBlur() {
    if (!this.options.includes(this.inputValue)) {
      this.inputValue = '';
      this.valueChange.emit('');
    }
    this.showList = false;
  }

  /** 名前入力フィルター */
  private filter(value: string): string[] {
    const v = this.normalizeKana(value);
    return this.options.filter((name) => this.normalizeKana(name).includes(v));
  }

  private normalizeKana(str: string): string {
    return str.replace(/[\u3041-\u3096]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) + 0x60));
  }
}
