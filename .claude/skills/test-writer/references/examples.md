# 保護パターン別コード例集

`SKILL.md` の3つの保護パターンそれぞれについて、JavaScript（Jest）と Ruby（RSpec）の対比例をまとめる。
❌ は抜け道が残る書き方、✅ はその抜け道を塞いだ書き方。

## パターン1: 実行状態の完全検証

### JavaScript (Jest)

```javascript
// ❌ 呼ばれたことしか検証していない
// （2回の発火・誤った引数・onErrorの発火がすべて通る）
expect(onSuccess).toHaveBeenCalled();

// ✅ 回数・引数・呼ばれない経路を固定する
expect(onSuccess).toHaveBeenCalledTimes(1);
expect(onSuccess).toHaveBeenCalledWith({ userId: 123 });
expect(onError).not.toHaveBeenCalled();
```

### Ruby (RSpec)

```ruby
# ❌ 呼ばれたことしか検証していない
# （2回の呼び出し・誤った引数・on_errorの呼び出しがすべて通る）
expect(on_success).to have_received(:call)

# ✅ 回数・引数・呼ばれない経路を固定する
# （`.with(...).once` だけでは引数が一致する呼び出ししか数えないため、
#   別の引数での追加の呼び出しが通ってしまう。総回数も固定する）
expect(on_success).to have_received(:call).once
expect(on_success).to have_received(:call).with(user_id: 123)
expect(on_error).not_to have_received(:call)
```

## パターン2: 期待値全体の検証

### 構造全体 — JavaScript (Jest)

```javascript
// ❌ フィールド単体しか検証していない
expect(result.id).toBe(1);
expect(result.name).toBe("Alice");
expect(result.role).toBe("member");

// ✅ 構造全体を固定する（意図しない変更はすべて失敗する）
expect(result).toStrictEqual({ id: 1, name: "Alice", role: "member" });

// ✅ フィールド単体に加えて、キーもチェックする
// （キーの過不足＝フィールドの欠落や意図しない追加も失敗する）
expect(Object.keys(result).sort()).toEqual(["id", "name", "role"]);
expect(result.id).toBe(1);
expect(result.name).toBe("Alice");
expect(result.role).toBe("member");
```

### 構造全体 — Ruby (RSpec)

```ruby
# ❌ フィールド単体しか検証していない
expect(result[:id]).to eq(1)
expect(result[:name]).to eq("Alice")
expect(result[:role]).to eq("member")

# ✅ 構造全体を固定する（意図しない変更はすべて失敗する）
expect(result).to eq({ id: 1, name: "Alice", role: "member" })

# ✅ フィールド単体に加えて、キーもチェックする
# （キーの過不足＝フィールドの欠落や意図しない追加も失敗する）
expect(result.keys).to contain_exactly(:id, :name, :role)
expect(result[:id]).to eq(1)
expect(result[:name]).to eq("Alice")
expect(result[:role]).to eq("member")
```

### コレクション — JavaScript (Jest)

```javascript
// ❌ 件数しか検証していない（中身が別物でも2件なら通る）
expect(result.items.length).toBe(2);

// ✅ 期待値の全体を固定する
// （商品・価格・合計のどれが壊れても失敗する）
expect(result).toStrictEqual({
  items: [
    { id: 1, name: "Coffee", price: 500 },
    { id: 2, name: "Beans", price: 1200 },
  ],
  total: 1700,
});
```

### コレクション — Ruby (RSpec)

```ruby
# ❌ 件数しか検証していない（中身が別物でも2件なら通る）
expect(result[:items].length).to eq(2)

# ✅ 期待値の全体を固定する（商品・価格・合計のどれが壊れても失敗する）
expect(result).to eq({
  items: [
    { id: 1, name: "Coffee", price: 500 },
    { id: 2, name: "Beans", price: 1200 }
  ],
  total: 1700
})
```

### 型と値の正確性 — JavaScript (Jest)

```javascript
// ❌ trueでなくても通ってしまう（"yes"や1でも通る）
expect(active).toBeTruthy();

// ✅ 正確な値と型を検証する
expect(active).toBe(true);
expect(count).toBe(0);
```

### 型と値の正確性 — Ruby (RSpec)

```ruby
# ❌ trueでなくても通ってしまう（"yes"や1でも通る）
expect(active?).to be_truthy

# ✅ 正確な値と型を検証する
expect(active?).to be true
expect(count).to eq 0
```

## パターン3: 外部境界のモック化

### JavaScript (Jest)

```javascript
// テスト対象の実装: 有効期限（現在時刻の7日後）を含むメール本文を組み立てる
const mailService = {
  createInviteMailBody(toEmail, inviteLink) {
    const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
    const expiryDate = expiresAt.toISOString().slice(0, 10); // 例: "2026-07-08"
    return `${toEmail}様\n${inviteLink}\nこのリンクの有効期限は ${expiryDate} です`;
  },
};

const expectedBody = `${toEmail}様\n${inviteLink}\nこのリンクの有効期限は 2026-07-08 です`;

// ❌ テスト対象そのものをモックしている
// （モックの返り値を検証するだけで、実装が壊れていても通る）
jest.spyOn(mailService, "createInviteMailBody").mockReturnValue(expectedBody);
expect(mailService.createInviteMailBody(toEmail, inviteLink)).toBe(expectedBody);

// ✅ 外部境界（現在時刻）だけをモックし、本物のロジックを動かす
// （有効期限が2026-07-08に確定し、実装にバグがあれば失敗する）
jest.useFakeTimers().setSystemTime(new Date("2026-07-01T00:00:00Z"));
expect(mailService.createInviteMailBody(toEmail, inviteLink)).toBe(expectedBody);
```

### Ruby (RSpec)

```ruby
# テスト対象の実装: 有効期限（現在時刻の7日後）を含むメール本文を組み立てる
class MailService
  def create_invite_mail_body(to_email, invite_link)
    expiry_date = (Time.zone.now + 7.days).strftime("%Y-%m-%d") # 例: "2026-07-08"
    "#{to_email}様\n#{invite_link}\nこのリンクの有効期限は #{expiry_date} です"
  end
end

expected_body = "#{to_email}様\n#{invite_link}\nこのリンクの有効期限は 2026-07-08 です"

# ❌ テスト対象そのものをモックしている
# （モックの返り値を検証するだけで、実装が壊れていても通る）
allow(mail_service).to receive(:create_invite_mail_body).and_return(expected_body)
expect(mail_service.create_invite_mail_body(to_email, invite_link)).to eq(expected_body)

# ✅ 外部境界（現在時刻）だけをモックし、本物のロジックを動かす
# （有効期限が2026-07-08に確定し、実装にバグがあれば失敗する）
travel_to Time.zone.local(2026, 7, 1) do
  expect(mail_service.create_invite_mail_body(to_email, invite_link)).to eq(expected_body)
end
```
