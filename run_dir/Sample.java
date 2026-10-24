/**
 * サンプル利用者のプロフィール情報を管理する。
 */
public class Sample {
    /** 利用者の表示名。 */
    private final String name;

    /** 利用者の年齢。 */
    private int age;

    /**
     * 名前と年齢を指定してプロフィールを作成する。
     *
     * @param name 利用者の表示名
     * @param age 利用者の年齢
     */
    public Sample(String name, int age) {
        this.name = name;
        this.age = age;
    }

    /**
     * 利用者の年齢を更新する。
     *
     * @param age 更新後の年齢
     */
    public void updateAge(int age) {
        this.age = age;
    }

    /**
     * 利用者の表示名と年齢を返す。
     *
     * @return プロフィールの説明
     */
    public String describe() {
        return name + " (" + age + ")";
    }
}
